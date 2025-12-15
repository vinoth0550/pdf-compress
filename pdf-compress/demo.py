
# # pdf compressor tool

# import os
# import io
# import shutil
# import tempfile
# from PIL import Image
# import pikepdf
# from pathlib import Path


# def setup_folders():
#     input_folder = Path("inputs")
#     output_folder = Path("outputs")
    
#     input_folder.mkdir(exist_ok=True)
#     output_folder.mkdir(exist_ok=True)
    
#     return input_folder, output_folder


# def compress_image_data(image_bytes, quality=60, max_dimension=1000):
#     try:
#         img = Image.open(io.BytesIO(image_bytes))
        
#         if img.mode in ('RGBA', 'LA'):
#             background = Image.new('RGB', img.size, (255, 255, 255))
#             if img.mode == 'RGBA':
#                 background.paste(img, mask=img.split()[3])
#             else:
#                 background.paste(img, mask=img.split()[1])
#             img = background
#         elif img.mode == 'P':
#             img = img.convert('RGB')
#         elif img.mode not in ('RGB', 'L'):
#             img = img.convert('RGB')
        
#         width, height = img.size
#         if width > max_dimension or height > max_dimension:
#             ratio = min(max_dimension / width, max_dimension / height)
#             new_size = (int(width * ratio), int(height * ratio))
#             img = img.resize(new_size, Image.Resampling.LANCZOS)
        
#         output = io.BytesIO()
#         img.save(output, format='JPEG', quality=quality, optimize=True)
        
#         return output.getvalue(), img.size
#     except Exception:
#         return None, None


# def compress_pdf(input_path, output_path, quality=55, max_dimension=900):
#     original_size = os.path.getsize(input_path)
    
#     temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
#     os.close(temp_fd)
    
#     try:
#         pdf = pikepdf.open(input_path)
#         images_processed = 0
        
#         for page in pdf.pages:
#             if '/Resources' not in page:
#                 continue
#             resources = page['/Resources']
#             if '/XObject' not in resources:
#                 continue
            
#             xobjects = resources['/XObject']
            
#             for name in list(xobjects.keys()):
#                 try:
#                     xobj = xobjects[name]
#                     if not isinstance(xobj, pikepdf.Stream):
#                         continue
                    
#                     if xobj.get('/Subtype') != pikepdf.Name.Image:
#                         continue
                    
#                     width = int(xobj.get('/Width', 0))
#                     height = int(xobj.get('/Height', 0))
                    
#                     if width < 50 or height < 50:
#                         continue
                    
#                     try:
#                         raw_size = len(xobj.read_raw_bytes())
                        
#                         filter_type = xobj.get('/Filter')
#                         if filter_type == pikepdf.Name.DCTDecode:
#                             image_data = xobj.read_raw_bytes()
#                         else:
#                             image_data = xobj.read_bytes()
                        
#                         compressed_data, new_size = compress_image_data(
#                             image_data, quality=quality, max_dimension=max_dimension
#                         )
                        
#                         if compressed_data and len(compressed_data) < raw_size * 0.85:
#                             new_stream = pikepdf.Stream(pdf, compressed_data)
#                             new_stream['/Type'] = pikepdf.Name.XObject
#                             new_stream['/Subtype'] = pikepdf.Name.Image
#                             new_stream['/Width'] = new_size[0]
#                             new_stream['/Height'] = new_size[1]
#                             new_stream['/ColorSpace'] = pikepdf.Name.DeviceRGB
#                             new_stream['/BitsPerComponent'] = 8
#                             new_stream['/Filter'] = pikepdf.Name.DCTDecode
                            
#                             xobjects[name] = new_stream
#                             images_processed += 1
                            
#                     except Exception:
#                         continue
                        
#                 except Exception:
#                     continue
        
#         pdf.save(
#             temp_path,
#             compress_streams=True,
#             object_stream_mode=pikepdf.ObjectStreamMode.generate
#         )
#         pdf.close()
        
#         compressed_size = os.path.getsize(temp_path)
        
#         if compressed_size < original_size:
#             shutil.copy2(temp_path, output_path)
#             return original_size, compressed_size
#         else:
#             shutil.copy2(input_path, output_path)
#             return original_size, original_size
            
#     finally:
#         if os.path.exists(temp_path):
#             os.remove(temp_path)


# def format_size(size_bytes):
#     if size_bytes < 1024:
#         return f"{size_bytes} B"
#     elif size_bytes < 1024 * 1024:
#         return f"{size_bytes / 1024:.2f} KB"
#     else:
#         return f"{size_bytes / (1024 * 1024):.2f} MB"


# def process_all_pdfs():
#     input_folder, output_folder = setup_folders()
    
#     pdf_files = list(input_folder.glob("*.pdf"))
    
#     if not pdf_files:
#         print(f"No PDF files found in '{input_folder}' folder.")
#         print(f"Please add PDF files to the '{input_folder}' folder and run again.")
#         return
    
#     print(f"Found {len(pdf_files)} PDF file(s) to compress.\n")
#     print("=" * 60)
    
#     total_original = 0
#     total_compressed = 0
    
#     for pdf_file in pdf_files:
#         output_file = output_folder / f"compressed_{pdf_file.name}"
        
#         print(f"\nProcessing: {pdf_file.name}")
        
#         try:
#             original_size, compressed_size = compress_pdf(str(pdf_file), str(output_file))
            
#             total_original += original_size
#             total_compressed += compressed_size
            
#             if compressed_size < original_size:
#                 reduction = ((original_size - compressed_size) / original_size) * 100
#                 print(f"  Original:   {format_size(original_size)}")
#                 print(f"  Compressed: {format_size(compressed_size)}")
#                 print(f"  Reduction:  {reduction:.1f}%")
#             else:
#                 print(f"  Size: {format_size(original_size)}")
#                 print(f"  Status: Already optimized (no reduction possible)")
            
#             print(f"  Saved to:   {output_file}")
            
#         except Exception as e:
#             print(f"  Error: {str(e)}")
    
#     print("\n" + "=" * 60)
#     print("SUMMARY")
#     print("=" * 60)
#     print(f"Total original size:   {format_size(total_original)}")
#     print(f"Total compressed size: {format_size(total_compressed)}")
#     if total_original > 0 and total_compressed < total_original:
#         total_reduction = ((total_original - total_compressed) / total_original) * 100
#         print(f"Total reduction:       {total_reduction:.1f}%")
#     print(f"\nCompressed files saved to '{output_folder}' folder.")


# def compress_single_pdf(input_path, output_path=None):
#     setup_folders()
    
#     if output_path is None:
#         output_folder = Path("outputs")
#         input_name = Path(input_path).name
#         output_path = str(output_folder / f"compressed_{input_name}")
    
#     print(f"Compressing: {input_path}")
    
#     original_size, compressed_size = compress_pdf(input_path, output_path)
    
#     if compressed_size < original_size:
#         reduction = ((original_size - compressed_size) / original_size) * 100
#         print(f"Original:   {format_size(original_size)}")
#         print(f"Compressed: {format_size(compressed_size)}")
#         print(f"Reduction:  {reduction:.1f}%")
#     else:
#         print(f"Size: {format_size(original_size)}")
#         print(f"Status: Already optimized (no reduction possible)")
    
#     print(f"Saved to:   {output_path}")
    
#     return output_path


# if __name__ == "__main__":
#     print("PDF Compressor Tool")
#     print("=" * 60)
#     print("This tool compresses PDF files (text and images)")
#     print("=" * 60 + "\n")
    
#     process_all_pdfs()


















# this code writed for adding counter for save logic and incresed 5 percentage compression to 30 percentage






# pdf compressor tool

import os
import io
import shutil
import tempfile
from PIL import Image
import pikepdf
from pathlib import Path


def setup_folders():
    input_folder = Path("inputs")
    output_folder = Path("outputs")
    
    input_folder.mkdir(exist_ok=True)
    output_folder.mkdir(exist_ok=True)
    
    return input_folder, output_folder


def compress_image_data(image_bytes, quality=60, max_dimension=1000):
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


# def compress_pdf(input_path, output_path, quality=55, max_dimension=900):

def compress_pdf(input_path, output_path, quality=45, max_dimension=700):


    original_size = os.path.getsize(input_path)
    
    temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
    os.close(temp_fd)
    
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
                        
                        # if compressed_data and len(compressed_data) < raw_size * 0.85:

                        if compressed_data and len(compressed_data) < raw_size * 0.75:

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
            temp_path,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate
        )
        pdf.close()
        
        compressed_size = os.path.getsize(temp_path)
        
        if compressed_size < original_size:
            shutil.copy2(temp_path, output_path)
            return original_size, compressed_size
        else:
            shutil.copy2(input_path, output_path)
            return original_size, original_size
            
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"







# for counter to save logics

def get_non_overwriting_path(path: Path) -> Path:
    """
    If path exists, append _1, _2, _3... before the file extension
    until a non-existing filename is found.
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1













def process_all_pdfs():
    input_folder, output_folder = setup_folders()
    
    pdf_files = list(input_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in '{input_folder}' folder.")
        print(f"Please add PDF files to the '{input_folder}' folder and run again.")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s) to compress.\n")
    print("=" * 60)
    
    total_original = 0
    total_compressed = 0
    
    for pdf_file in pdf_files:

        # output_file = output_folder / f"compressed_{pdf_file.name}"

        base_output_file = output_folder / f"compressed_{pdf_file.name}"
        output_file = get_non_overwriting_path(base_output_file)

        
        print(f"\nProcessing: {pdf_file.name}")
        
        try:
            original_size, compressed_size = compress_pdf(str(pdf_file), str(output_file))
            
            total_original += original_size
            total_compressed += compressed_size
            
            if compressed_size < original_size:
                reduction = ((original_size - compressed_size) / original_size) * 100
                print(f"  Original:   {format_size(original_size)}")
                print(f"  Compressed: {format_size(compressed_size)}")
                print(f"  Reduction:  {reduction:.1f}%")
            else:
                print(f"  Size: {format_size(original_size)}")
                print(f"  Status: Already optimized (no reduction possible)")
            
            print(f"  Saved to:   {output_file}")
            
        except Exception as e:
            print(f"  Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total original size:   {format_size(total_original)}")
    print(f"Total compressed size: {format_size(total_compressed)}")
    if total_original > 0 and total_compressed < total_original:
        total_reduction = ((total_original - total_compressed) / total_original) * 100
        print(f"Total reduction:       {total_reduction:.1f}%")
    print(f"\nCompressed files saved to '{output_folder}' folder.")


def compress_single_pdf(input_path, output_path=None):
    setup_folders()
    
    if output_path is None:
        output_folder = Path("outputs")
        input_name = Path(input_path).name

        # output_path = str(output_folder / f"compressed_{input_name}")

        base_output_path = output_folder / f"compressed_{input_name}"
        output_path = str(get_non_overwriting_path(base_output_path))

    



    print(f"Compressing: {input_path}")
    
    original_size, compressed_size = compress_pdf(input_path, output_path)
    
    if compressed_size < original_size:
        reduction = ((original_size - compressed_size) / original_size) * 100
        print(f"Original:   {format_size(original_size)}")
        print(f"Compressed: {format_size(compressed_size)}")
        print(f"Reduction:  {reduction:.1f}%")
    else:
        print(f"Size: {format_size(original_size)}")
        print(f"Status: Already optimized (no reduction possible)")
    
    print(f"Saved to:   {output_path}")
    
    return output_path


if __name__ == "__main__":
    print("PDF Compressor Tool")
    print("=" * 60)
    print("This tool compresses PDF files (text and images)")
    print("=" * 60 + "\n")
    
    process_all_pdfs()
