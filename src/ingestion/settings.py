from pathlib import Path

DEFAULT_RAW_DIR = Path(r"K:\Certificat course\AI-powered chatbot\raw")
DEFAULT_OUT_DIR = Path("storage/stage1")

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".pptm",
    ".xls",
    ".xlsx",
    ".csv",
    ".tsv",
    ".txt",
    ".md",
    ".rst",
    ".rtf",
    ".html",
    ".htm",
    ".xml",
    ".json",
    ".epub",
    ".odt",
    ".org",
    ".eml",
    ".msg",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tiff",
    ".tif",
    ".heic",
}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".idea",
    ".vscode",
}