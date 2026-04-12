from typing import List

class ChunkSplitter:
    TARGET_TOKENS = 512
    OVERLAP_TOKENS = 50

    @classmethod
    def split_text(cls, text: str, max_tokens: int = None) -> List[dict]:
        if not text or len(text.strip()) < 100:
            return []
        max_tokens = max_tokens or cls.TARGET_TOKENS
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks, current_chunk, current_tokens = [], [], 0
        for para in paragraphs:
            para_tokens = len(para) // 4
            if current_tokens + para_tokens > max_tokens and current_chunk:
                chunks.append({"texte": "\n\n".join(current_chunk), "token_count": current_tokens})
                overlap = current_chunk[-(cls.OVERLAP_TOKENS // 10):] if len(current_chunk) > 1 else []
                current_chunk = overlap
                current_tokens = sum(len(c) // 4 for c in overlap)
            current_chunk.append(para)
            current_tokens += para_tokens
        if current_chunk:
            chunks.append({"texte": "\n\n".join(current_chunk), "token_count": current_tokens})
        return chunks
