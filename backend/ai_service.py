# backend/ai_service.py
import logging
from typing import List, Dict
from sqlalchemy.orm import Session
from openai import OpenAI
import crud

logger = logging.getLogger("affiliate_ai")


def get_client(api_key: str, base_url: str = "https://api.deepseek.com") -> OpenAI:
    """
    Trả về OpenAI client tương thích DeepSeek (OpenAI SDK v1).
    """
    return OpenAI(api_key=api_key, base_url=base_url)


async def suggest_products_with_config(
    query: str,
    products: List[Dict],
    db: Session,
    provider: str = "deepseek",
) -> str:
    """
    Gợi ý sản phẩm dựa trên danh sách products và cấu hình AI trong DB theo 'provider'.
    - Lấy config bằng crud.get_api_config(db, provider) (theo name, ví dụ 'deepseek').
    - Gọi API theo chuẩn OpenAI Chat Completions.
    """
    # Lấy đúng 1 config theo name
    config = crud.get_api_config(db, provider)
    if not config:
        return f"⚠️ Chưa cấu hình API cho provider: {provider}. Hãy POST /api-configs hoặc /api-configs/upsert."

    # Rút gọn danh sách sản phẩm đưa vào prompt
    items = []
    for p in products[:40]:
        name = p.get("name", "")
        aff = p.get("affiliate_url") or p.get("url") or ""
        items.append(f"- {name}: {aff}")
    product_text = "\n".join(items) if items else "(chưa có sản phẩm)"

    system_prompt = "Bạn là trợ lý AI chuyên tư vấn & gợi ý sản phẩm bằng tiếng Việt, ngắn gọn, rõ ràng."
    user_prompt = (
        f"Người dùng hỏi: {query}\n\n"
        f"Danh sách sản phẩm (tối đa 40):\n{product_text}\n\n"
        "Yêu cầu: Hãy chọn các sản phẩm phù hợp nhất, giải thích ngắn gọn (2–3 câu) và chèn link affiliate tương ứng."
    )

    try:
        client = get_client(api_key=config.api_key, base_url=config.base_url or "https://api.deepseek.com")

        resp = client.chat.completions.create(
            model=(config.model or "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=400,
        )

        return resp.choices[0].message.content

    except Exception as e:
        logger.exception("AI request failed")
        return f"Lỗi khi gọi AI ({provider}): {str(e)}"
