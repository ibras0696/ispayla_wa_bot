from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from .db import Base


# 🧑‍💼 User - таблица пользователей
class User(Base):
    """
    Модель пользователя. Используется Whatsapp sender ID в качестве основного ключа.
    """
    __tablename__ = "users"

    sender = Column(String(50), primary_key=True, unique=True, nullable=False, index=True)  # Whatsapp ID
    username = Column(String(100), nullable=True)  # Имя пользователя (необязательно)
    registered_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))  # Дата регистрации
    balance = Column(Integer, default=0)  # Баланс пользователя

    ads = relationship("Ad", back_populates="owner")  # Объявления пользователя
    views = relationship("ViewLog", back_populates="viewer")  # Просмотры объявлений пользователем
    favorites = relationship("Favorite", back_populates="user")  # Избранные объявления


# 🚗 Ad — Объявления о продаже автомобилей
class Ad(Base):
    """
    Объявления о продаже автомобилей.
    """
    __tablename__ = 'ads'

    id = Column(Integer, primary_key=True, index=True)  # Автоинкрементный ID объявления
    sender = Column(String(50), ForeignKey('users.sender'))  # Whatsapp ID владельца
    title = Column(String(100), nullable=False)  # Название объявления
    description = Column(Text, nullable=False)  # Подробности объявления
    price = Column(Integer, nullable=False)  # Цена автомобиля
    year_car = Column(Integer, nullable=False)  # Год выпуска автомобиля
    car_brand_id = Column(Integer, ForeignKey('car_brands.id'), index=True)  # Марка авто
    mileage_km_car = Column(Integer, nullable=False)  # Пробег в км
    vin_number = Column(String(100), nullable=False, unique=True, index=True)  # Уникальный VIN-номер
    day_count = Column(Integer, default=0)  # Количество дней публикации
    is_active = Column(Boolean, default=False)  # Активно ли объявление
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))  # Время публикации объявления

    # Отношения
    owner = relationship("User", back_populates="ads")  # Владелец объявления
    brand = relationship("CarBrand", back_populates="ads")  # Марка автомобиля
    images = relationship("AdImage", back_populates="ad", cascade="all, delete-orphan")  # Изображения объявления
    moderation = relationship("Moderation", back_populates="ad", uselist=False,
                              cascade="all, delete-orphan")  # Модерация объявления
    views = relationship("ViewLog", back_populates="ad", cascade="all, delete-orphan")  # Просмотры объявления
    favorites = relationship("Favorite", back_populates="ad", cascade="all, delete-orphan")  # Избранные объявления


# 🚘 CarBrand — Марка автомобиля
class CarBrand(Base):
    __tablename__ = "car_brands"

    id = Column(Integer, primary_key=True)  # Автоинкрементный ID марки
    name = Column(String(100), unique=True, nullable=False)  # Название марки

    ads = relationship("Ad", back_populates="brand")  # Объявления с этой маркой


# 📁 AdImage
class AdImage(Base):
    __tablename__ = "ad_images"

    id = Column(Integer, primary_key=True)  # Автоинкрементный ID изображения
    ad_id = Column(Integer, ForeignKey("ads.id"))  # ID объявления
    image_url = Column(String, nullable=False)  # URL изображения
    uploaded_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))  # Дата загрузки изображения

    ad = relationship("Ad", back_populates="images")  # Объявление, к которому относится изображение


# 📌 Favorite — Избранные объявления
class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)  # Автоинкрементный ID избранного
    sender = Column(String(50), ForeignKey("users.sender"))  # ID пользователя, добавившего в избранное
    ad_id = Column(Integer, ForeignKey("ads.id"))  # ID объявления, добавленного в избранное
    added_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))  # Дата добавления в избранное

    user = relationship("User", back_populates="favorites")  # Пользователь, добавивший в избранное
    ad = relationship("Ad", back_populates="favorites")  # Объявление, добавленное в избранное


# 🧾 Payment — Платежи
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)  # Автоинкрементный ID платежа
    sender = Column(String(50), ForeignKey("users.sender"))  # ID пользователя, совершившего платеж
    amount = Column(Integer, nullable=False)  # Сумма платежа
    payment_date = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))  # Дата платежа
    description = Column(Text, nullable=True)  # Описание платежа (необязательно)

    user = relationship("User")  # Пользователь, совершивший платеж


# Отдельная таблица Модераторов в ТГ
class Moderator(Base):
    __tablename__ = "moderators"

    id = Column(Integer, primary_key=True)  # Автоинкрементный ID модератора
    telegram_id = Column(Integer, unique=True, nullable=False)  # Whatsapp ID модератора
    username = Column(String(100), nullable=True)  # Имя пользователя (необязательно)
    registered_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))  # Дата регистрации
    is_active = Column(Boolean, default=True)  # Активен ли модератор

    moderations = relationship("Moderation", back_populates="moderator")  # Модерации, выполненные этим модератором


# 🔎 Moderation — модерация объявлений
class Moderation(Base):
    __tablename__ = "moderations"

    id = Column(Integer, primary_key=True)  # Автоинкрементный ID модерации
    ad_id = Column(Integer, ForeignKey("ads.id"), unique=True)  # ID объявления, которое проверяется
    moderator_id = Column(Integer, ForeignKey("moderators.id"),
                          nullable=True)  # ID модератора, который проверяет (может быть None, если еще не проверено)
    status = Column(String(20), default="pending")  # pending / approved / rejected
    comment = Column(Text, nullable=True)  # Почему отклонили (если отклонено)
    checked_at = Column(DateTime(timezone=True), nullable=True, default=None)  # Дата проверки (если проверено)

    ad = relationship("Ad", back_populates="moderation")
    moderator = relationship("Moderator", back_populates="moderations")

    # Статический метод информация по статусам
    @staticmethod
    def get_status_info(status: str) -> tuple:
        """
        Получить информацию по статусу модерации.
        :param status: Статус модерации (pending, approved, rejected)
        :return: Кортеж с заголовком и описанием статуса
        """
        status_info = {
            "pending": ("Ожидает проверки", "Модератор еще не проверил это объявление."),
            "approved": ("Одобрено", "Объявление прошло модерацию и опубликовано."),
            "rejected": ("Отклонено", "Объявление не прошло модерацию. Проверьте комментарий.")
        }
        return status_info.get(status, ("Неизвестный статус", "Статус не найден."))


# 👁️ ViewLog — просмотры объявлений
class ViewLog(Base):
    __tablename__ = "view_logs"

    id = Column(Integer, primary_key=True)  # Автоинкрементный ID просмотра
    ad_id = Column(Integer, ForeignKey("ads.id"))  # ID объявления, которое просмотрели
    sender = Column(String(50), ForeignKey("users.sender"),
                    nullable=False)  # Whatsapp ID пользователя, который просмотрел (может быть None, если анонимный просмотр)
    viewed_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))  # Дата просмотра

    ad = relationship("Ad", back_populates="views")  # Объявление, которое просмотрели
    viewer = relationship("User",
                          back_populates="views")  # Пользователь, который просмотрел (может быть None, если анонимный просмотр)
