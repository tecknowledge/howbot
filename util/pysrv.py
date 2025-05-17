# TODO: Add API-Key
import subprocess, os

from flask import Flask, request, jsonify

app = Flask(__name__)
def execute_python_code(code):
    try:
        # Write the code to a temporary file
        # TODO: Create a random file and allow it to be referenced later
        with open('temp_code.py', 'w') as f:
            f.write(code)

        # Execute the code in a subprocess and capture the output
        result = subprocess.run(['python', 'temp_code.py'], capture_output=True, text=True, timeout=30)

        # Clean up the temporary file
        os.remove('temp_code.py')

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {"error": "Code execution timed out"}
    except Exception as e:
        return {"error": str(e)}

@app.route('/api/python', methods=['POST'])
def execute_code():
    print('Request:')
    data = request.get_json()
    code = data.get('code', '')

    print('Code:',code)
    if not code:
        return jsonify({"error": "No code provided"}), 400

    result = execute_python_code(code)

    return jsonify(result)

if __name__ == '__main__':
    app.run()
