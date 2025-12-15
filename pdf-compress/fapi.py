import os
import io
import shutil
import tempfile
import subprocess
from PIL import Image
import pikepdf
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uuid
from datetime import datetime

app = FastAPI(title="PDF Compressor API")

# Setup static files for downloads
DOWNLOAD_FOLDER = Path("downloads")
DOWNLOAD_FOLDER.mkdir(exist_ok=True)

# Mount the downloads folder to serve files
app.mount("/files", StaticFiles(directory=DOWNLOAD_FOLDER), name="files")


def setup_folders():
    input_folder = Path("inputs")
    output_folder = Path("outputs")
    
    input_folder.mkdir(exist_ok=True)
    output_folder.mkdir(exist_ok=True)
    
    return input_folder, output_folder


def compress_with_ghostscript(input_path, output_path, setting="ebook"):
    """
    Ghostscript PDF compression with different quality settings:
    - screen: lowest quality, smallest size (72 dpi)
    - ebook: medium quality, good compression (150 dpi) 
    - printer: high quality, less compression (300 dpi)
    - prepress: highest quality, minimal compression
    """
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5",
        f"-dPDFSETTINGS=/{setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dMonoImageDownsampleType=/Bicubic",
        "-dOptimize=true",
        f"-sOutputFile={output_path}",
        input_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0
    except Exception:
        return False


def compress_with_ghostscript_aggressive(input_path, output_path):
    """Even more aggressive compression with screen quality"""
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/screen",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        "-dColorImageResolution=100",
        "-dGrayImageResolution=100",
        "-dMonoImageResolution=100",
        "-dOptimize=true",
        f"-sOutputFile={output_path}",
        input_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0
    except Exception:
        return False


def compress_image_data(image_bytes, quality=50, max_dimension=800):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img, mask=img.split()[1])
            img = background
        elif img.mode == 'P':
            img = img.convert('RGB')
        elif img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            ratio = min(max_dimension / width, max_dimension / height)
            new_size = (int(width * ratio), int(height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        
        return output.getvalue(), img.size
    except Exception:
        return None, None


def compress_with_pikepdf(input_path, output_path, quality=50, max_dimension=800):
    
    try:
        pdf = pikepdf.open(input_path)
        images_processed = 0
        
        for page in pdf.pages:
            if '/Resources' not in page:
                continue
            resources = page['/Resources']
            if '/XObject' not in resources:
                continue
            
            xobjects = resources['/XObject']
            
            for name in list(xobjects.keys()):
                try:
                    xobj = xobjects[name]
                    if not isinstance(xobj, pikepdf.Stream):
                        continue
                    
                    if xobj.get('/Subtype') != pikepdf.Name.Image:
                        continue
                    
                    width = int(xobj.get('/Width', 0))
                    height = int(xobj.get('/Height', 0))
                    
                    if width < 50 or height < 50:
                        continue
                    
                    try:
                        raw_size = len(xobj.read_raw_bytes())
                        
                        filter_type = xobj.get('/Filter')
                        if filter_type == pikepdf.Name.DCTDecode:
                            image_data = xobj.read_raw_bytes()
                        else:
                            image_data = xobj.read_bytes()
                        
                        compressed_data, new_size = compress_image_data(
                            image_data, quality=quality, max_dimension=max_dimension
                        )
                        
                        if compressed_data and len(compressed_data) < raw_size * 0.9:
                            new_stream = pikepdf.Stream(pdf, compressed_data)
                            new_stream['/Type'] = pikepdf.Name.XObject
                            new_stream['/Subtype'] = pikepdf.Name.Image
                            new_stream['/Width'] = new_size[0]
                            new_stream['/Height'] = new_size[1]
                            new_stream['/ColorSpace'] = pikepdf.Name.DeviceRGB
                            new_stream['/BitsPerComponent'] = 8
                            new_stream['/Filter'] = pikepdf.Name.DCTDecode
                            
                            xobjects[name] = new_stream
                            images_processed += 1
                            
                    except Exception:
                        continue
                        
                except Exception:
                    continue
        
        pdf.save(
            output_path,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            recompress_flate=True
        )
        pdf.close()
        return True
    except Exception:
        return False


def compress_pdf(input_path, output_path, target_reduction=0.25):

    original_size = os.path.getsize(input_path)
    
    temp_dir = tempfile.mkdtemp()
    temp_gs_ebook = os.path.join(temp_dir, "gs_ebook.pdf")
    temp_gs_screen = os.path.join(temp_dir, "gs_screen.pdf")
    temp_pikepdf = os.path.join(temp_dir, "pikepdf.pdf")
    
    results = []
    
    try:
        if compress_with_ghostscript(input_path, temp_gs_ebook, "ebook"):
            size = os.path.getsize(temp_gs_ebook)
            results.append(("ghostscript_ebook", temp_gs_ebook, size))
        
        if compress_with_ghostscript_aggressive(input_path, temp_gs_screen):
            size = os.path.getsize(temp_gs_screen)
            results.append(("ghostscript_screen", temp_gs_screen, size))
        
        if compress_with_pikepdf(input_path, temp_pikepdf, quality=45, max_dimension=700):
            size = os.path.getsize(temp_pikepdf)
            results.append(("pikepdf", temp_pikepdf, size))
        
        if not results:
            shutil.copy2(input_path, output_path)
            return original_size, original_size
        
        results.sort(key=lambda x: x[2])
        best_name, best_path, best_size = results[0]
        
        if best_size < original_size:
            shutil.copy2(best_path, output_path)
            return original_size, best_size
        else:
            shutil.copy2(input_path, output_path)
            return original_size, original_size
            
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


#  FastAPI Routes

@app.get("/")
async def root():
    """Welcome endpoint"""
    return {
        "status": "success",
        "message": "PDF Compressor API is running",
        "version": "1.0.0"
    }


@app.post("/compress")
async def compress_pdf_endpoint(file: UploadFile = File(...)):

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Only PDF files are allowed"
            }
        )
    
    temp_input = None
    output_file = None
    
    try:
        # Create temporary input file
        temp_dir = tempfile.mkdtemp()
        temp_input = os.path.join(temp_dir, file.filename)
        
        # Save uploaded file to temporary location
        file_content = await file.read()
        with open(temp_input, 'wb') as f:
            f.write(file_content)
        
        # Create output filename with unique UUID
        unique_id = str(uuid.uuid4())
        output_filename = f"{unique_id}.pdf"
        output_file = DOWNLOAD_FOLDER / output_filename
        
        # Compress the PDF
        original_size, compressed_size = compress_pdf(str(temp_input), str(output_file))
        
        # Calculate reduction percentage
        if compressed_size < original_size:
            reduction = ((original_size - compressed_size) / original_size) * 100
        else:
            reduction = 0
        
        # Generate download link
        download_link = f"http://127.0.0.1:8000/files/{output_filename}"
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "PDF successfully compressed!",
                "download_link": download_link,
                "details": {
                    "original_size": format_size(original_size),
                    "compressed_size": format_size(compressed_size),
                    "reduction_percentage": f"{reduction:.1f}%"
                }
            }
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Error processing PDF: {str(e)}"
            }
        )
    
    finally:
        # Cleanup temporary files
        if temp_input and os.path.exists(temp_input):
            try:
                shutil.rmtree(os.path.dirname(temp_input), ignore_errors=True)
            except:
                pass


@app.post("/compress-pdf")
async def compress_multiple_pdfs(files: list[UploadFile] = File(...)):

    
    # Validate files
    if not files:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "No files provided"
            }
        )
    
    invalid_files = [f.filename for f in files if not f.filename.lower().endswith('.pdf')]
    if invalid_files:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": f"Only PDF files are allowed. Invalid files: {', '.join(invalid_files)}"
            }
        )
    
    results = []
    total_original = 0
    total_compressed = 0
    
    try:
        for file in files:
            temp_input = None
            try:
                # Create temporary input file
                temp_dir = tempfile.mkdtemp()
                temp_input = os.path.join(temp_dir, file.filename)
                
                # Save uploaded file
                file_content = await file.read()
                with open(temp_input, 'wb') as f:
                    f.write(file_content)
                
                # Create output filename
                unique_id = str(uuid.uuid4())
                output_filename = f"{unique_id}.pdf"
                output_file = DOWNLOAD_FOLDER / output_filename
                
                # Compress the PDF
                original_size, compressed_size = compress_pdf(str(temp_input), str(output_file))
                
                total_original += original_size
                total_compressed += compressed_size
                
                # Calculate reduction
                if compressed_size < original_size:
                    reduction = ((original_size - compressed_size) / original_size) * 100
                else:
                    reduction = 0
                
                download_link = f"http://127.0.0.1:8000/files/{output_filename}"
                
                results.append({
                    "original_filename": file.filename,
                    "download_link": download_link,
                    "original_size": format_size(original_size),
                    "compressed_size": format_size(compressed_size),
                    "reduction_percentage": f"{reduction:.1f}%"
                })
                
            except Exception as e:
                results.append({
                    "original_filename": file.filename,
                    "status": "error",
                    "message": str(e)
                })
            
            finally:
                if temp_input and os.path.exists(temp_input):
                    try:
                        shutil.rmtree(os.path.dirname(temp_input), ignore_errors=True)
                    except:
                        pass
        
        total_reduction = 0
        if total_original > 0 and total_compressed < total_original:
            total_reduction = ((total_original - total_compressed) / total_original) * 100
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "PDFs successfully compressed!",
                "files": results
         

                }
            
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Error processing PDFs: {str(e)}"
            }
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
