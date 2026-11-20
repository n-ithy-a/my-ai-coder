# aihelper

Free-tier AI coding helper. Discovers currently available models from Gemini, Groq and
OpenRouter, routes through LiteLLM, and falls back automatically when one fails.

## Install (Colab / Kaggle)

    !pip install -q git+https://github.com/<your-username>/aihelper.git
    from aihelper import ask, code, fix, set_project

## Keys (never put these in the repo)

Add `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` as:
- Colab: Secrets (key icon), notebook access ON
- Kaggle: Add-ons > Secrets, and Internet ON
- Local / VS Code: environment variables or a `.env` you export

## Use

    set_project("Goal: ... Data: ... Libraries: ...")
    code("load the data and show missing values")
    fix(error_text, broken_code)
    ask("explain this concept")

    %%ai
    explain what a confusion matrix is
