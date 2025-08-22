import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from pybit.unified_trading import HTTP
import json

class LiquidationSignalValidator:
    def __init__(self, flask_app_url="http://127.0.0.1:5000", use_testnet=False):
        """
        Initialize the validator with Flask app URL and Bybit session
        """
        self.flask_app_url = flask_app_url
        self.session = HTTP(testnet=use_testnet)
        
    def get_liquidation_data(self):
        """
        Fetch liquidation data from the Flask application
        """
        try:
            response = requests.get(f"{self.flask_app_url}/liquidations", timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching liquidation data: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error connecting to Flask app: {e}")
            return []
    
    def get_kline_data(self, symbol, interval="5", limit=200):
        """
        Fetch K-line data from Bybit for a given symbol
        """
        try:
            # Convert symbol format if needed (e.g., BTCUSD -> BTCUSDT for spot)
            formatted_symbol = self.format_symbol(symbol)
            
            response = self.session.get_kline(
                category="linear",  # Using USDT perpetual contracts
                symbol=formatted_symbol,
                interval=interval,
                limit=limit
            )
            
            if response['retCode'] == 0:
                klines = response['result']['list']
                # Convert to DataFrame for easier manipulation
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
                ])
                
                # Convert string values to float
                for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                    df[col] = df[col].astype(float)
                
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                df = df.sort_values('timestamp').reset_index(drop=True)
                
                return df
            else:
                print(f"Error fetching K-line data for {symbol}: {response['retMsg']}")
                return None
                
        except Exception as e:
            print(f"Error getting K-line data for {symbol}: {e}")
            return None
    
    def format_symbol(self, symbol):
        """
        Format symbol for Bybit API (convert to USDT perpetual format)
        """
        # Remove any trailing numbers or special characters
        base_symbol = ''.join(filter(str.isalpha, symbol))
        
        # Common symbol mappings
        if base_symbol.endswith('USD') and not base_symbol.endswith('USDT'):
            base_symbol = base_symbol.replace('USD', 'USDT')
        elif not base_symbol.endswith('USDT'):
            base_symbol += 'USDT'
            
        return base_symbol
    
    def calculate_pivot_points(self, df, period=3):
        """
        Calculate pivot highs and lows
        """
        df = df.copy()
        
        # Calculate pivot highs
        df['pivot_high'] = np.nan
        df['pivot_low'] = np.nan
        
        for i in range(period, len(df) - period):
            # Check for pivot high
            is_pivot_high = True
            for j in range(i - period, i + period + 1):
                if j != i and df.loc[j, 'high'] >= df.loc[i, 'high']:
                    is_pivot_high = False
                    break
            if is_pivot_high:
                df.loc[i, 'pivot_high'] = df.loc[i, 'high']
            
            # Check for pivot low
            is_pivot_low = True
            for j in range(i - period, i + period + 1):
                if j != i and df.loc[j, 'low'] <= df.loc[i, 'low']:
                    is_pivot_low = False
                    break
            if is_pivot_low:
                df.loc[i, 'pivot_low'] = df.loc[i, 'low']
        
        return df
    
    def calculate_center_line(self, df):
        """
        Calculate center line using pivot points with weighted calculation
        """
        df = df.copy()
        df['center'] = np.nan
        
        center = None
        
        for i in range(len(df)):
            # Get last pivot point (high or low)
            lastpp = None
            if not pd.isna(df.loc[i, 'pivot_high']):
                lastpp = df.loc[i, 'pivot_high']
            elif not pd.isna(df.loc[i, 'pivot_low']):
                lastpp = df.loc[i, 'pivot_low']
            
            if lastpp is not None:
                if center is None:
                    center = lastpp
                else:
                    # Weighted calculation: (center * 2 + lastpp) / 3
                    center = (center * 2 + lastpp) / 3
            
            df.loc[i, 'center'] = center
        
        # Forward fill the center line
        df['center'] = df['center'].fillna(method='ffill')
        
        return df
    
    def calculate_williams_vix_fix(self, df, pd_period=22, bbl=20, mult=2.0, lb=50, phw=0.85):
        """
        Calculate Williams VIX Fix for bottom detection and modified version for top detection
        """
        df = df.copy()
        
        # Williams VIX Fix for bottoms
        df['highest_close'] = df['close'].rolling(window=pd_period).max()
        df['wvf'] = ((df['highest_close'] - df['low']) / df['highest_close']) * 100
        
        df['wvf_sma'] = df['wvf'].rolling(window=bbl).mean()
        df['wvf_std'] = df['wvf'].rolling(window=bbl).std()
        
        df['upper_band'] = df['wvf_sma'] + (mult * df['wvf_std'])
        df['lower_band'] = df['wvf_sma'] - (mult * df['wvf_std'])
        df['range_high'] = df['wvf'].rolling(window=lb).max() * phw
        
        # Modified Williams VIX Fix for tops
        df['lowest_close'] = df['close'].rolling(window=pd_period).min()
        df['wvf1'] = ((df['lowest_close'] - df['high']) / df['lowest_close']) * 100
        
        df['wvf1_sma'] = df['wvf1'].rolling(window=bbl).mean()
        df['wvf1_std'] = df['wvf1'].rolling(window=bbl).std()
        
        df['upper_band1'] = df['wvf1_sma'] + (mult * df['wvf1_std'])
        df['lower_band1'] = df['wvf1_sma'] - (mult * df['wvf1_std'])
        df['range_low1'] = df['wvf1'].rolling(window=lb).min() * phw
        
        return df
    
    def generate_signals(self, df):
        """
        Generate buy/sell signals based on the PineScript logic
        """
        df = df.copy()
        
        # Calculate all indicators
        df = self.calculate_pivot_points(df)
        df = self.calculate_center_line(df)
        df = self.calculate_williams_vix_fix(df)
        
        # Generate signals
        df['top_alert'] = (
            ((df['wvf1'] <= df['lower_band1']) | (df['wvf1'] <= df['range_low1'])) &
            (df['close'] > df['open']) &
            (df['low'] > df['center'])
        )
        
        df['bottom_alert'] = (
            ((df['wvf'] >= df['upper_band']) | (df['wvf'] >= df['range_high'])) &
            (df['close'] < df['open']) &
            (df['high'] < df['center'])
        )
        
        # Convert to signal strings
        df['indicator_signal'] = 'none'
        df.loc[df['top_alert'], 'indicator_signal'] = 'short'
        df.loc[df['bottom_alert'], 'indicator_signal'] = 'long'
        
        return df
    
    def validate_signals(self, liquidation_threshold=50000):
        """
        Main function to validate liquidation signals against indicator signals
        """
        print("Fetching liquidation data...")
        liquidations = self.get_liquidation_data()
        
        if not liquidations:
            print("No liquidation data available")
            return
        
        # Filter liquidations by threshold
        liquidations = [liq for liq in liquidations 
                       if self.parse_turnover(liq.get('Value', '0')) >= liquidation_threshold]
        
        print(f"Found {len(liquidations)} liquidations above threshold")
        
        results = []
        
        for liq in liquidations:
            symbol = liq['Symbol']
            liq_signal = liq['Signal']
            liq_value = liq['Value']
            
            print(f"\nProcessing {symbol} - Liquidation Signal: {liq_signal}")
            
            # Get K-line data
            kline_data = self.get_kline_data(symbol)
            
            if kline_data is None or len(kline_data) < 50:
                print(f"Insufficient K-line data for {symbol}")
                continue
            
            # Generate indicator signals
            df_with_signals = self.generate_signals(kline_data)
            
            # Get the latest signal from indicator
            latest_signals = df_with_signals[df_with_signals['indicator_signal'] != 'none'].tail(5)
            
            if len(latest_signals) > 0:
                latest_indicator_signal = latest_signals.iloc[-1]['indicator_signal']
                signal_time = latest_signals.iloc[-1]['timestamp']
                
                # Compare signals
                match = (liq_signal == latest_indicator_signal)
                
                result = {
                    'symbol': symbol,
                    'liquidation_signal': liq_signal,
                    'indicator_signal': latest_indicator_signal,
                    'liquidation_value': liq_value,
                    'match': match,
                    'signal_time': signal_time,
                    'latest_price': df_with_signals.iloc[-1]['close']
                }
                
                results.append(result)
                
                print(f"Liquidation: {liq_signal} | Indicator: {latest_indicator_signal} | Match: {match}")
            else:
                print(f"No recent indicator signals for {symbol}")
            
            # Add small delay to avoid rate limiting
            time.sleep(0.5)
        
        # Calculate accuracy
        if results:
            matches = sum(1 for r in results if r['match'])
            accuracy = (matches / len(results)) * 100
            
            print(f"\n{'='*50}")
            print(f"VALIDATION RESULTS")
            print(f"{'='*50}")
            print(f"Total comparisons: {len(results)}")
            print(f"Matches: {matches}")
            print(f"Accuracy: {accuracy:.2f}%")
            print(f"{'='*50}")
            
            # Detailed results
            print("\nDetailed Results:")
            for result in results:
                status = "✓" if result['match'] else "✗"
                print(f"{status} {result['symbol']}: Liq({result['liquidation_signal']}) vs Ind({result['indicator_signal']}) - ${result['liquidation_value']}")
        
        return results
    
    def parse_turnover(self, turnover_str):
        """
        Parse turnover string and convert to float value
        """
        try:
            turnover_str = turnover_str.strip().replace(',', '')
            if 'K' in turnover_str:
                return float(turnover_str.replace('K', '')) * 1000
            elif 'M' in turnover_str:
                return float(turnover_str.replace('M', '')) * 1000000
            else:
                return float(turnover_str)
        except:
            return 0


def main():
    """
    Main execution function
    """
    # Initialize validator
    validator = LiquidationSignalValidator(
        flask_app_url="http://127.0.0.1:5000",  # Update with your Flask app URL
        use_testnet=False  # Set to True for testnet
    )
    
    # Set liquidation threshold (minimum turnover value)
    liquidation_threshold = 20000  # $20K minimum
    
    print("Starting Liquidation Signal Validation...")
    print(f"Liquidation threshold: ${liquidation_threshold:,}")
    
    # Run validation
    results = validator.validate_signals(liquidation_threshold)
    
    # Optionally save results to file
    if results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"validation_results_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to {filename}")


if __name__ == "__main__":
    main()