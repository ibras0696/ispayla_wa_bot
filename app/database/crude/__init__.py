from .add import CrudeAdd
from .car_brand import CrudeCarBrand
from .favorite import CrudeFavorite
from .moder import CrudeModerator, CrudeModeration
from .payment import CrudePayment
from .user import CrudeUser
from .car_image import CrudeAdImage
from .view import CrudeViewLog
from .manager import CrudManager

# Удобный синглтон менеджера (можно использовать напрямую)
crud_manager = CrudManager()


__all__ = [
    "CrudeAdd",
    "CrudeCarBrand",
    "CrudeFavorite",
    "CrudeModerator",
    "CrudeModeration",
    "CrudePayment",
    "CrudeUser",
    "CrudeAdImage",
    "CrudeViewLog",
    "CrudManager",
    "crud_manager",
]