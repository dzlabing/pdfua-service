import os
import subprocess
import tempfile
from flask import Flask, request, render_template, send_file, jsonify

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size


def convert_to_pdfua(input_pdf_path, output_pdf_path):
    """
    Convert PDF to PDF/UA using Ghostscript only
    Returns (success: bool, message: str)
    """
    try:
        # Use Ghostscript for PDF/UA conversion
        gs_cmd = [
            'gs', '-dPDFA', '-dPDFUA', '-dNOPAUSE', '-dBATCH',
            '-sColorConversionStrategy=UseDeviceIndependentColor',
            '-sDEVICE=pdfwrite',
            '-dPDFACompatibilityPolicy=2',
            '-dCompatibilityLevel=1.7',
            '-dDetectDuplicateImages=true',
            '-dCompressPages=true',
            '-dCompressFonts=true',
            f'-sOutputFile={output_pdf_path}',
            input_pdf_path
        ]

        gs_result = subprocess.run(gs_cmd, capture_output=True, text=True)

        if gs_result.returncode == 0:
            # Check if output file was created and has content
            if os.path.exists(output_pdf_path) and os.path.getsize(output_pdf_path) > 0:
                return True, "PDF successfully converted with PDF/UA flags"
            else:
                return False, "Conversion completed but output file is empty"
        else:
            error_msg = gs_result.stderr or "Unknown Ghostscript error"
            # Extract the most relevant error line
            error_lines = [line for line in error_msg.split('\n') if line.strip() and 'error' in line.lower()]
            if error_lines:
                error_msg = error_lines[0]
            return False, f"Conversion failed: {error_msg}"

    except Exception as e:
        return False, f"Conversion error: {str(e)}"


def allowed_file(filename):
    """Check if the file has a PDF extension"""
    return '.' in filename and filename.lower().endswith('.pdf')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert_pdf():
    # Check if file was uploaded
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['pdf_file']

    # Check if file is selected
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Check if file is PDF
    if not allowed_file(file.filename):
        return jsonify({'error': 'File must be a PDF'}), 400

    # Create temporary files
    input_path = None
    output_path = None

    try:
        # Create temporary input file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as input_temp:
            input_path = input_temp.name
            file.save(input_path)

        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as output_temp:
            output_path = output_temp.name

        # Convert to PDF/UA
        success, message = convert_to_pdfua(input_path, output_path)

        if success:
            # Return the converted file for download
            download_name = f"pdfua_{file.filename}"
            return send_file(
                output_path,
                as_attachment=True,
                download_name=download_name,
                mimetype='application/pdf'
            )
        else:
            return jsonify({'error': message}), 500

    except Exception as e:
        return jsonify({'error': f'Processing error: {str(e)}'}), 500
    finally:
        # Clean up temporary files
        try:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)
            if output_path and os.path.exists(output_path):
                # Only delete output file if we're returning an error
                if not success:
                    os.unlink(output_path)
                # If success, the file will be deleted after being sent by send_file
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")


@app.errorhandler(413)
def handle_file_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413


@app.errorhandler(500)
def handle_internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(404)
def handle_not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)