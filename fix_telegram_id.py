#!/usr/bin/env python
"""Скрипт для исправления типа telegram_id в существующей БД"""
from sqlalchemy import create_engine, text
import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_telegram_id_type():
    """Изменяет тип колонки telegram_id с INTEGER на BIGINT"""
    engine = create_engine(config.DATABASE_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            # Проверяем текущий тип
            result = conn.execute(text("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'telegram_id'
            """))
            
            current_type = result.scalar()
            logger.info(f"Текущий тип telegram_id: {current_type}")
            
            if current_type == 'bigint':
                logger.info("Тип уже BIGINT, изменения не требуются")
                return
            
            # Изменяем тип колонки
            logger.info("Изменяю тип telegram_id на BIGINT...")
            conn.execute(text("ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT"))
            conn.commit()
            logger.info("✅ Тип telegram_id успешно изменен на BIGINT")
            
    except Exception as e:
        logger.error(f"Ошибка при изменении типа: {e}")
        raise

if __name__ == '__main__':
    fix_telegram_id_type()

