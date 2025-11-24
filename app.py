import os
import subprocess
import tempfile
from flask import Flask, request, render_template, send_file, jsonify

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size


def convert_to_pdfua(input_pdf_path, output_pdf_path):
    """
    Convert PDF to PDF/UA using veraPDF and Ghostscript
    Returns (success: bool, message: str)
    """
    try:
        # Check if veraPDF is available for validation
        try:
            subprocess.run(['verapdf', '--version'], capture_output=True, check=True)
            vera_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            vera_available = False

        # Use Ghostscript for PDF/UA conversion
        gs_cmd = [
            'gs', '-dPDFA', '-dPDFUA', '-dNOPAUSE', '-dBATCH',
            '-sColorConversionStrategy=UseDeviceIndependentColor',
            '-sDEVICE=pdfwrite', '-dPDFACompatibilityPolicy=2',
            '-dCompatibilityLevel=1.7',
            f'-sOutputFile={output_pdf_path}',
            input_pdf_path
        ]

        gs_result = subprocess.run(gs_cmd, capture_output=True, text=True)

        if gs_result.returncode == 0:
            if vera_available:
                # Validate the converted file with veraPDF
                validate_cmd = [
                    'verapdf',
                    '--flavour', 'pdfua-1',
                    output_pdf_path
                ]

                validate_result = subprocess.run(validate_cmd, capture_output=True, text=True)

                # veraPDF returns 1 for compliant, 0 for non-compliant
                if validate_result.returncode == 1:
                    return True, "Successfully converted to PDF/UA (validated)"
                else:
                    return True, "Conversion completed but file may not be fully PDF/UA compliant"
            else:
                return True, "Conversion completed (veraPDF not available for validation)"
        else:
            error_msg = gs_result.stderr or "Unknown Ghostscript error"
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
    input_temp = None
    output_temp = None

    try:
        # Create temporary files with explicit cleanup
        input_temp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        input_path = input_temp.name
        input_temp.close()  # Close so we can write to it

        output_temp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        output_path = output_temp.name
        output_temp.close()  # Close so Ghostscript can write to it

        # Save uploaded file to temporary location
        file.save(input_path)

        # Convert to PDF/UA
        success, message = convert_to_pdfua(input_path, output_path)

        if success:
            # Return the converted file for download
            download_name = f"converted_{file.filename}"
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
                # Only delete output file if we're not returning it
                if not success:
                    os.unlink(output_path)
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