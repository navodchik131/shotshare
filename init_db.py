#!/usr/bin/env python
"""Скрипт для инициализации базы данных"""
from database import init_db, engine
from database.models import Base

if __name__ == '__main__':
    print("Создание таблиц в базе данных...")
    Base.metadata.create_all(bind=engine)
    print("База данных инициализирована!")

