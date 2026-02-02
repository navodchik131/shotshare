from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import ProgrammingError, OperationalError
import config
import logging

logger = logging.getLogger(__name__)

engine = create_engine(config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _check_enum_exists(conn, enum_name):
    """Проверяет существование ENUM типа в PostgreSQL"""
    try:
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_type 
                WHERE typname = :enum_name
            )
        """), {"enum_name": enum_name})
        return result.scalar()
    except Exception as e:
        logger.debug(f"Ошибка при проверке ENUM {enum_name}: {e}")
        return False

def init_db():
    """Инициализация базы данных с обработкой ошибок существующих типов"""
    try:
        # Проверяем, существует ли хотя бы одна таблица
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            logger.info("База данных уже инициализирована, пропускаем создание таблиц")
            return
        
        # Создаем таблицы только если их нет
        # checkfirst=True проверяет существование таблиц перед созданием
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("База данных успешно инициализирована")
        
    except (ProgrammingError, OperationalError) as e:
        error_str = str(e).lower()
        # Игнорируем ошибки о существующих типах ENUM или таблицах
        if any(keyword in error_str for keyword in [
            "already exists", 
            "duplicate key", 
            "pg_type_typname_nsp_index",
            "relation already exists"
        ]):
            logger.info("Некоторые объекты БД уже существуют, это нормально при повторном запуске")
            # Пытаемся создать только недостающие таблицы
            try:
                Base.metadata.create_all(bind=engine, checkfirst=True)
                logger.info("Проверка и создание недостающих таблиц завершено")
            except Exception as e2:
                # Если все еще ошибка, возможно БД уже полностью инициализирована
                logger.info(f"База данных уже содержит все необходимые объекты: {e2}")
        else:
            logger.error(f"Ошибка при инициализации БД: {e}")
            raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при инициализации БД: {e}")
        raise

