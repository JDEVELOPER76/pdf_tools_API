from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse , StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import conversiones as convert
import os
import sys
import zipfile
import tempfile

app = FastAPI(title="SuperPDF",description="PDF tools",version="1A")

def get_resource_path(relative_path: str) -> str:
    """
    Devuelve la ruta absoluta de recursos en desarrollo y en ejecutable (PyInstaller).
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

static_dir = get_resource_path("static")
templates_dir = get_resource_path("templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# rutas del fronted 
@app.get("/",response_class = HTMLResponse)
async def inicio(request: Request):
    return templates.TemplateResponse("index.html", {"request":request})

@app.get("/word-to-pdf",response_class = HTMLResponse)
async def word_to_pdf(request: Request):
    return templates.TemplateResponse("word-to-pdf.html", {"request":request})

@app.get("/pdf-to-word",response_class = HTMLResponse)
async def pdf_to_word(request : Request):
    return templates.TemplateResponse("pdf-to-word.html", {"request":request})

@app.get("/pdf-to-pptx",response_class = HTMLResponse)
async def pdf_to_pptx(request : Request):
    return templates.TemplateResponse("pdf-to-pptx.html", {"request":request})

@app.get("/pptx-to-pdf",response_class = HTMLResponse)
async def pptx_to_pdf(request : Request):
    return templates.TemplateResponse("pptx-to-pdf.html", {"request":request})

@app.get("/split-pdf",response_class = HTMLResponse)
async def split_pdf(request : Request):
    return templates.TemplateResponse("split-pdf.html", {"request":request})

@app.get("/merge-pdf",response_class = HTMLResponse)
async def merge_pdf(request : Request):
    return templates.TemplateResponse("merge-pdf.html", {"request":request})

@app.get("/delete-pages", response_class=HTMLResponse)
async def delete_pages_form(request: Request):
    return templates.TemplateResponse("delete-pages.html", {"request": request})


#metodos post
@app.post("/convert-word-to-pdf")
async def convert_word_to_pdf(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    valid_files = []
    errors = []
    for file in files:
        if file.filename.lower().endswith(('.doc', '.docx')):
            valid_files.append(file)
        else:
            errors.append(f"'{file.filename}' no es un documento Word válido. Se omite.")

    if not valid_files:
        raise HTTPException(status_code=400, detail="No se encontraron archivos .doc o .docx. " + "; ".join(errors))

    # Caso 1: un solo archivo -> PDF directo
    if len(valid_files) == 1:
        file = valid_files[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            word_temp_path = os.path.join(tmpdir, file.filename)
            content = await file.read()
            with open(word_temp_path, "wb") as f:
                f.write(content)

            base_name = os.path.splitext(file.filename)[0]
            safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip() or "documento"
            pdf_path = os.path.join(tmpdir, f"{safe_base}.pdf")

            try:
                convert.convertir_word_a_pdf(word_temp_path, pdf_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error al convertir '{file.filename}': {str(e)}")

            with open(pdf_path, "rb") as f:
                pdf_data = f.read()

        return StreamingResponse(
            iter([pdf_data]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={safe_base}.pdf",
                "X-Warnings": "; ".join(errors) if errors else ""
            }
        )

    # Caso 2: múltiples archivos -> ZIP
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_files = []
        for idx, file in enumerate(valid_files, start=1):
            filename = file.filename
            word_temp_path = os.path.join(tmpdir, f"input_{idx}_{filename}")
            content = await file.read()
            with open(word_temp_path, "wb") as f:
                f.write(content)

            base_name = os.path.splitext(filename)[0]
            safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if not safe_base:
                safe_base = f"documento_{idx}"
            pdf_path = os.path.join(tmpdir, f"{safe_base}.pdf")

            try:
                convert.convertir_word_a_pdf(word_temp_path, pdf_path)
                pdf_files.append((f"{safe_base}.pdf", pdf_path))
            except Exception as e:
                errors.append(f"Error al convertir '{filename}': {str(e)}")

        if not pdf_files:
            raise HTTPException(status_code=400, detail="No se pudo convertir ningún archivo. " + "; ".join(errors))

        zip_buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        try:
            with zipfile.ZipFile(zip_buffer.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for pdf_name, pdf_path in pdf_files:
                    zipf.write(pdf_path, arcname=pdf_name)
            zip_buffer.close()
            with open(zip_buffer.name, "rb") as f:
                zip_data = f.read()
            error_msg = "; ".join(errors) if errors else ""
            return StreamingResponse(
                iter([zip_data]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": "attachment; filename=convertidos_word_a_pdf.zip",
                    "X-Warnings": error_msg[:500]
                }
            )
        finally:
            if os.path.exists(zip_buffer.name):
                os.unlink(zip_buffer.name)

@app.post("/convert-pdf-to-word")
async def convert_pdf_to_word(files: list[UploadFile] = File(...)):
    """
    Recibe uno o varios archivos PDF.
    - Si hay 1 archivo: devuelve un .docx directamente.
    - Si hay varios: devuelve un ZIP con todos los .docx.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    valid_files = []
    errors = []
    for file in files:
        if file.filename.lower().endswith('.pdf'):
            valid_files.append(file)
        else:
            errors.append(f"'{file.filename}' no es un PDF válido. Se omite.")

    if not valid_files:
        raise HTTPException(status_code=400, detail="No se encontraron archivos .pdf. " + "; ".join(errors))

    # Caso 1: un solo archivo -> Word directo
    if len(valid_files) == 1:
        file = valid_files[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_temp_path = os.path.join(tmpdir, file.filename)
            content = await file.read()
            with open(pdf_temp_path, "wb") as f:
                f.write(content)

            base_name = os.path.splitext(file.filename)[0]
            safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip() or "documento"
            word_path = os.path.join(tmpdir, f"{safe_base}.docx")

            try:
                convert.convertir_pdf_word(pdf_temp_path, word_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error al convertir '{file.filename}': {str(e)}")

            with open(word_path, "rb") as f:
                word_data = f.read()

        return StreamingResponse(
            iter([word_data]),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={safe_base}.docx",
                "X-Warnings": "; ".join(errors) if errors else ""
            }
        )

    # Caso 2: múltiples archivos -> ZIP
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_files = []  # lista de (nombre, ruta)
        for idx, file in enumerate(valid_files, start=1):
            filename = file.filename
            pdf_temp_path = os.path.join(tmpdir, f"input_{idx}_{filename}")
            content = await file.read()
            with open(pdf_temp_path, "wb") as f:
                f.write(content)

            base_name = os.path.splitext(filename)[0]
            safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if not safe_base:
                safe_base = f"documento_{idx}"
            word_path = os.path.join(tmpdir, f"{safe_base}.docx")

            try:
                convert.convertir_pdf_word(pdf_temp_path, word_path)
                docx_files.append((f"{safe_base}.docx", word_path))
            except Exception as e:
                errors.append(f"Error al convertir '{filename}': {str(e)}")

        if not docx_files:
            raise HTTPException(status_code=400, detail="No se pudo convertir ningún archivo. " + "; ".join(errors))

        zip_buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        try:
            with zipfile.ZipFile(zip_buffer.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for docx_name, docx_path in docx_files:
                    zipf.write(docx_path, arcname=docx_name)
            zip_buffer.close()
            with open(zip_buffer.name, "rb") as f:
                zip_data = f.read()
            error_msg = "; ".join(errors) if errors else ""
            return StreamingResponse(
                iter([zip_data]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": "attachment; filename=convertidos_pdf_a_word.zip",
                    "X-Warnings": error_msg[:500]
                }
            )
        finally:
            if os.path.exists(zip_buffer.name):
                os.unlink(zip_buffer.name)

@app.post("/convert-pdf-to-pptx")
async def convert_pdf_to_pptx(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    valid_files = []
    errors = []
    for file in files:
        if file.filename.lower().endswith('.pdf'):
            valid_files.append(file)
        else:
            errors.append(f"'{file.filename}' no es un PDF válido. Se omite.")

    if not valid_files:
        raise HTTPException(status_code=400, detail="No se encontraron archivos .pdf. " + "; ".join(errors))

    # Caso 1: un solo archivo -> PPTX directo
    if len(valid_files) == 1:
        file = valid_files[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_temp_path = os.path.join(tmpdir, file.filename)
            content = await file.read()
            with open(pdf_temp_path, "wb") as f:
                f.write(content)

            base_name = os.path.splitext(file.filename)[0]
            safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip() or "presentacion"
            pptx_path = os.path.join(tmpdir, f"{safe_base}.pptx")

            try:
                convert.convertir_pdf_a_pptx(pdf_temp_path, pptx_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error al convertir '{file.filename}': {str(e)}")

            with open(pptx_path, "rb") as f:
                pptx_data = f.read()

        return StreamingResponse(
            iter([pptx_data]),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f"attachment; filename={safe_base}.pptx",
                "X-Warnings": "; ".join(errors) if errors else ""
            }
        )

    # Caso 2: múltiples archivos -> ZIP
    with tempfile.TemporaryDirectory() as tmpdir:
        pptx_files = []
        for idx, file in enumerate(valid_files, start=1):
            filename = file.filename
            pdf_temp_path = os.path.join(tmpdir, f"input_{idx}_{filename}")
            content = await file.read()
            with open(pdf_temp_path, "wb") as f:
                f.write(content)

            base_name = os.path.splitext(filename)[0]
            safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if not safe_base:
                safe_base = f"presentacion_{idx}"
            pptx_path = os.path.join(tmpdir, f"{safe_base}.pptx")

            try:
                convert.convertir_pdf_a_pptx(pdf_temp_path, pptx_path)
                pptx_files.append((f"{safe_base}.pptx", pptx_path))
            except Exception as e:
                errors.append(f"Error al convertir '{filename}': {str(e)}")

        if not pptx_files:
            raise HTTPException(status_code=400, detail="No se pudo convertir ningún archivo. " + "; ".join(errors))

        zip_buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        try:
            with zipfile.ZipFile(zip_buffer.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for pptx_name, pptx_path in pptx_files:
                    zipf.write(pptx_path, arcname=pptx_name)
            zip_buffer.close()
            with open(zip_buffer.name, "rb") as f:
                zip_data = f.read()
            error_msg = "; ".join(errors) if errors else ""
            return StreamingResponse(
                iter([zip_data]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": "attachment; filename=convertidos_pdf_a_pptx.zip",
                    "X-Warnings": error_msg[:500]
                }
            )
        finally:
            if os.path.exists(zip_buffer.name):
                os.unlink(zip_buffer.name)
                
@app.post("/convert-pptx-to-pdf")
async def convert_pptx_to_pdf(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    valid_files = []
    errors = []
    for file in files:
        if file.filename.lower().endswith('.pptx'):
            valid_files.append(file)
        else:
            errors.append(f"'{file.filename}' no es un PPTX válido. Se omite.")

    if not valid_files:
        raise HTTPException(status_code=400, detail="No se encontraron archivos .pptx. " + "; ".join(errors))

    # Caso 1: un solo archivo -> PDF directo
    if len(valid_files) == 1:
        file = valid_files[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            pptx_temp_path = os.path.join(tmpdir, file.filename)
            content = await file.read()
            with open(pptx_temp_path, "wb") as f:
                f.write(content)

            base_name = os.path.splitext(file.filename)[0]
            safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip() or "presentacion"
            pdf_path = os.path.join(tmpdir, f"{safe_base}.pdf")

            try:
                convert.convertir_pptx_pdf(pptx_temp_path, pdf_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error al convertir '{file.filename}': {str(e)}")

            with open(pdf_path, "rb") as f:
                pdf_data = f.read()

        return StreamingResponse(
            iter([pdf_data]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={safe_base}.pdf",
                "X-Warnings": "; ".join(errors) if errors else ""
            }
        )

    # Caso 2: múltiples archivos -> ZIP
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_files = []
        for idx, file in enumerate(valid_files, start=1):
            filename = file.filename
            pptx_temp_path = os.path.join(tmpdir, f"input_{idx}_{filename}")
            content = await file.read()
            with open(pptx_temp_path, "wb") as f:
                f.write(content)

            base_name = os.path.splitext(filename)[0]
            safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if not safe_base:
                safe_base = f"presentacion_{idx}"
            pdf_path = os.path.join(tmpdir, f"{safe_base}.pdf")

            try:
                convert.convertir_pptx_pdf(pptx_temp_path, pdf_path)
                pdf_files.append((f"{safe_base}.pdf", pdf_path))
            except Exception as e:
                errors.append(f"Error al convertir '{filename}': {str(e)}")

        if not pdf_files:
            raise HTTPException(status_code=400, detail="No se pudo convertir ningún archivo. " + "; ".join(errors))

        zip_buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        try:
            with zipfile.ZipFile(zip_buffer.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for pdf_name, pdf_path in pdf_files:
                    zipf.write(pdf_path, arcname=pdf_name)
            zip_buffer.close()
            with open(zip_buffer.name, "rb") as f:
                zip_data = f.read()
            error_msg = "; ".join(errors) if errors else ""
            return StreamingResponse(
                iter([zip_data]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": "attachment; filename=convertidos_pptx_a_pdf.zip",
                    "X-Warnings": error_msg[:500]
                }
            )
        finally:
            if os.path.exists(zip_buffer.name):
                os.unlink(zip_buffer.name)

@app.post("/split-pdf")
async def split_pdf(
    file: UploadFile = File(...),
    inicio: int = Form(...),
    fin: int = Form(...)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser PDF")

    if inicio < 1 or fin < 1:
        raise HTTPException(status_code=400, detail="Las páginas deben ser mayores a 0")
    if inicio > fin:
        raise HTTPException(status_code=400, detail="La página inicial no puede ser mayor que la final")

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, file.filename)
        content = await file.read()
        with open(pdf_path, "wb") as f:
            f.write(content)

        reader = convert.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        if inicio > total_pages or fin > total_pages:
            raise HTTPException(status_code=400, detail=f"El PDF solo tiene {total_pages} páginas.")

        base_name = os.path.splitext(file.filename)[0]
        safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip() or "documento"
        output_pdf = os.path.join(tmpdir, f"{safe_base}_paginas_{inicio}_a_{fin}.pdf")

        try:
            convert.extraer_paginas(pdf_path, output_pdf, inicio, fin)  # Usa tu función
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

        with open(output_pdf, "rb") as f:
            pdf_data = f.read()

    return StreamingResponse(
        iter([pdf_data]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={safe_base}_paginas_{inicio}_a_{fin}.pdf"
        }
    )


@app.post("/merge-pdf")
async def merge_pdf(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    valid_files = []
    errors = []
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            errors.append(f"'{file.filename}' no es PDF, se omite.")
        else:
            valid_files.append(file)

    if not valid_files:
        raise HTTPException(status_code=400, detail="No se encontraron PDFs válidos. " + "; ".join(errors))

    with tempfile.TemporaryDirectory() as tmpdir:
        # Guardar cada PDF en el disco temporal
        pdf_paths = []
        for idx, file in enumerate(valid_files):
            path = os.path.join(tmpdir, f"{idx}_{file.filename}")
            content = await file.read()
            with open(path, "wb") as f:
                f.write(content)
            pdf_paths.append(path)

        # Usar tu función unir_pdf (espera lista de rutas)
        try:
            writer = convert.unir_pdf(pdf_paths)   # Devuelve PdfWriter
            output_pdf = os.path.join(tmpdir, "merged.pdf")
            with open(output_pdf, "wb") as f:
                writer.write(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al unir PDFs: {str(e)}")

        # Leer el PDF resultante
        with open(output_pdf, "rb") as f:
            pdf_data = f.read()

    return StreamingResponse(
        iter([pdf_data]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=documento_unido.pdf"}
    )

@app.post("/delete-pages")
async def delete_pages(
    file: UploadFile = File(...),
    paginas: str = Form(...),       # ej: "4,9" o "1-3,5,8-10"
    modo: str = Form("eliminar")    # "eliminar" o "conservar"
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser PDF")
    if modo not in ("eliminar", "conservar"):
        raise HTTPException(status_code=400, detail="Modo no válido. Use 'eliminar' o 'conservar'")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Guardar PDF subido
        pdf_path = os.path.join(tmpdir, file.filename)
        content = await file.read()
        with open(pdf_path, "wb") as f:
            f.write(content)

        # Nombre de salida seguro
        base_name = os.path.splitext(file.filename)[0]
        safe_base = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip() or "documento"
        output_pdf = os.path.join(tmpdir, f"{safe_base}_modificado.pdf")

        try:
            convert.eliminar_paginas_personalizado(
                pdf_entrada=pdf_path,
                pdf_salida=output_pdf,
                especificacion=paginas,
                modo=modo
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

        with open(output_pdf, "rb") as f:
            pdf_data = f.read()

    accion = "eliminadas" if modo == "eliminar" else "conservadas"
    return StreamingResponse(
        iter([pdf_data]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={safe_base}_paginas_{accion}.pdf"
        }
    )
