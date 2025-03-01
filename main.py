import logging
from flask import Flask, render_template

app = Flask(__name__)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)

@app.route('/')
def index():
  return render_template('index.html')

if __name__ == '__main__':
  app.run(port=5000)
