from flask import Flask
import os
from flask import Flask, jsonify, request
from app.routers import liquidation
from dotenv import load_dotenv

app = Flask(__name__)

app.register_blueprint(liquidation.bp)

@app.route('/')
def hello():
    return 'Hello, World! Crypto server'

if __name__ == "__main__":
    app.run(debug=True)