"""
FastAPI 主入口 - AI 求职助手后端服务
"""
import os
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.services.docx_parser import parse_docx, parse_jd_text
from backend.services.ai_service import ai_service
from backend.services.resume_generator import generate_resume_docx
from backend.services.ppt_generator import generate_ppt

app = FastAPI(title="AI 求职助手", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 输出目录
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR = BASE_DIR.parent / "static"


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AI 求职助手"}


@app.post("/api/run")
async def run_pipeline(
    resume_file: UploadFile = File(None),
    jd_file: UploadFile = File(None),
    jd_text: str = Form(""),
    api_key: str = Form(""),
    api_base_url: str = Form(""),
    api_model: str = Form(""),
):
    """
    主流程：上传简历 + JD，生成所有输出
    """
    task_id = str(uuid.uuid4())[:8]
    task_dir = OUTPUT_DIR / task_id
    task_dir.mkdir(exist_ok=True)

    # 从请求参数或环境变量获取 API 配置
    effective_api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not effective_api_key:
        raise HTTPException(400, "请设置 API Key（在页面左侧展开 API 设置，输入你的 OpenAI API Key）")

    # 更新 AI 服务配置
    ai_service.set_config(
        api_key=effective_api_key,
        base_url=api_base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        model=api_model or os.environ.get("AI_MODEL", "gpt-4o"),
    )

    try:
        # ── 1. 解析简历 ──
        if resume_file is None:
            raise HTTPException(400, "请上传简历文件")

        resume_path = task_dir / f"resume_{resume_file.filename}"
        with open(resume_path, "wb") as f:
            content = await resume_file.read()
            f.write(content)

        if resume_file.filename.endswith(".docx"):
            parsed = parse_docx(str(resume_path))
            resume_text = parsed["full_text"]
        elif resume_file.filename.endswith(".txt"):
            with open(resume_path, "r", encoding="utf-8") as f:
                resume_text = f.read()
        else:
            raise HTTPException(400, "简历文件仅支持 .docx 或 .txt 格式")

        if not resume_text.strip():
            raise HTTPException(400, "简历内容为空，请检查文件")

        # ── 2. 解析JD ──
        if jd_file:
            jd_path = task_dir / f"jd_{jd_file.filename}"
            with open(jd_path, "wb") as f:
                content = await jd_file.read()
                f.write(content)

            if jd_file.filename.endswith(".txt"):
                with open(jd_path, "r", encoding="utf-8") as f:
                    jd_text = f.read()
            elif jd_file.filename.endswith(".docx"):
                parsed_jd = parse_docx(str(jd_path))
                jd_text = parsed_jd["full_text"]
        elif jd_text:
            jd_text = parse_jd_text(jd_text)
        else:
            raise HTTPException(400, "请上传岗位JD文件或粘贴JD内容")

        if not jd_text.strip():
            raise HTTPException(400, "JD内容为空，请检查")

        # ── 3. AI 生成优化简历 ──
        updated_resume = await ai_service.generate_updated_resume(resume_text, jd_text)

        # 生成简历 DOCX
        resume_output = task_dir / "优化简历.docx"
        generate_resume_docx(updated_resume, str(resume_output))

        # ── 4. AI 生成 PPT 内容 ──
        ppt_content = await ai_service.generate_ppt_content(resume_text, jd_text)

        # 生成 PPTX
        ppt_output = task_dir / "面试PPT.pptx"
        generate_ppt(ppt_content, str(ppt_output))

        # ── 5. AI 生成面试讲稿 ──
        script_text = await ai_service.generate_script(resume_text, jd_text, ppt_content)

        script_output = task_dir / "面试讲稿.txt"
        with open(script_output, "w", encoding="utf-8") as f:
            f.write(script_text)

        # ── 6. AI 生成面试提问 ──
        questions = await ai_service.generate_interview_questions(resume_text, jd_text)

        questions_output = task_dir / "面试提问.json"
        import json
        with open(questions_output, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)

        return {
            "task_id": task_id,
            "resume_text": updated_resume,
            "ppt_content": ppt_content,
            "script_text": script_text,
            "questions": questions,
            "downloads": {
                "resume_docx": f"/api/download/{task_id}/优化简历.docx",
                "ppt": f"/api/download/{task_id}/面试PPT.pptx",
                "script": f"/api/download/{task_id}/面试讲稿.txt",
                "questions": f"/api/download/{task_id}/面试提问.json",
            },
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        # 清理临时文件
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"处理失败: {str(e)}")


@app.get("/api/download/{task_id}/{filename}")
async def download_file(task_id: str, filename: str):
    """下载生成的文件"""
    file_path = OUTPUT_DIR / task_id / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在或已过期")

    # 根据文件类型设置 media_type
    if filename.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif filename.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif filename.endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "text/plain"

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )


# 静态文件
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)