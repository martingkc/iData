from sqlalchemy import UUID


def make_thread_id(user_id: UUID, chat_id: UUID) -> str:
    return f"user:{user_id}:chat:{chat_id}"