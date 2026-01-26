Auth


POST
/api/auth/token
Получить токен доступа


POST
/api/auth/register
Регистрация нового пользователя


GET
/api/auth/me
Получить информацию о текущем пользователе


Users


PUT
/api/users/me
Обновить информацию о текущем пользователе



GET
/api/users/{user_id}
Получить пользователя по ID



DELETE
/api/users/{user_id}
Удалить пользователя



GET
/api/users
Получить список пользователей



PUT
/api/users/{user_id}/activate
Активировать пользователя



PUT
/api/users/{user_id}/deactivate
Деактивировать пользователя



PUT
/api/users/{user_id}/verify-email
Подтвердить email пользователя



GET
/api/users/search/{email}
Поиск пользователя по email


Products


GET
/api/products
Получить список продуктов


POST
/api/products
Создать новый продукт



GET
/api/products/slug/{slug}
Получить продукт по slug


PUT
/api/products/base/{product_id}
Обновить базовый продукт



DELETE
/api/products/base/{product_id}
Удалить продукт



GET
/api/products/{product_id}/colors
Список цветов продукта


POST
/api/products/{product_id}/colors
Добавить цвет



PUT
/api/products/colors/{color_id}
Обновить цвет



DELETE
/api/products/colors/{color_id}
Удалить цвет



GET
/api/products/colors/{product_color_id}/images
Список изображений продукта


POST
/api/products/colors/{product_color_id}/images
Загрузить изображение



POST
/api/products/colors/{product_color_id}/primary-image
Загрузить главное изображение



PUT
/api/products/colors/{product_color_id}/images/reorder
Изменить порядок изображений



DELETE
/api/products/images/{image_id}
Удалить изображение



GET
/api/products/colors/{product_color_id}/sizes
Список размеров продукта


POST
/api/products/colors/{product_color_id}/sizes
Добавить размер



PUT
/api/products/sizes/{size_id}
Обновить размер



DELETE
/api/products/sizes/{size_id}
Удалить размер



PUT
/api/products/colors/{product_color_id}/sizes/reorder
Изменить порядок размеров



GET
/api/products/{product_id}/sections
Получить все аккордеоны товара


POST
/api/products/{product_id}/sections
Добавить новый аккордеон



PUT
/api/products/sections/{section_id}
Обновить существующий заголовок или контент



DELETE
/api/products/sections/{section_id}
Удалить аккордеон



PUT
/api/products/{product_id}/sections/reorder
Массовое обновление sort_order



POST
/api/products/base/{product_id}/categories
Добавить продукт в категорию



PUT
/api/products/base/{product_id}/categories
Установить категории продукта



GET
/api/products/base/{product_id}/categories
Получить категории продукта


DELETE
/api/products/base/{product_id}/categories/{category_id}
Удалить продукт из категории



POST
/api/products/base/{product_id}/collections
Добавить продукт в коллекцию



DELETE
/api/products/base/{product_id}/collections/{collection_id}
Удалить продукт из коллекции



GET
/api/products/{product_id}
Получить продукт по ID


GET
/api/products/{category_slug}/{slug}
Получить продукт по категории и slug

Categories


GET
/api/categories
Дерево категорий


POST
/api/categories
Создать категорию



GET
/api/categories/{slug}
Продукты по категории


DELETE
/api/categories/{category_id}
Удалить категорию



PUT
/api/categories/{category_id}/products/reorder
Изменить порядок товаров в категории


Collections


GET
/api/collections
Получить список коллекций


POST
/api/collections
Создать коллекцию



GET
/api/collections/{collection_id}
Получить коллекцию по ID


PUT
/api/collections/{collection_id}
Обновить коллекцию



DELETE
/api/collections/{collection_id}
Удалить коллекцию



GET
/api/collections/{collection_id}/products
Получить продукты коллекции


POST
/api/collections/{collection_id}/images
Добавить изображение в коллекцию



DELETE
/api/collections/images/{image_id}
Удалить изображение коллекции


Orders


POST
/api/orders
Создать заказ



GET
/api/orders
Получить список заказов



GET
/api/orders/{order_id}
Получить заказ по ID



PUT
/api/orders/{order_id}
Обновить заказ



POST
/api/orders/test_add_order_to_cdek
Тестовый endpoint: добавить заказ в CDEK


CDEK


GET
/api/cdek/suggest_cities
Получить список городов по названию


GET
/api/cdek/offices
Получить список пунктов выдачи по коду города


GET
/api/cdek/order/{uuid}
Получить информацию о заказе по UUID


GET
/api/cdek/waybill
Получить URL накладной


GET
/api/cdek/barcode
Получить URL штрихкода