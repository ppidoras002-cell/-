import aiosqlite
import secrets
import string

from config import DB_NAME


# ============================================================
# DATABASE INIT
# ============================================================

async def init_db():

    async with aiosqlite.connect(DB_NAME) as db:

        # ====================================================
        # USERS
        # ====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Roulette fields migration
        cursor = await db.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in await cursor.fetchall()]
        if "roulette_discount" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN roulette_discount INTEGER DEFAULT 0")
        if "roulette_last_spin" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN roulette_last_spin TEXT DEFAULT NULL")
        if "referral_balance" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN referral_balance REAL DEFAULT 0")
        if "referred_by" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL")
        if "payout_details" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN payout_details TEXT DEFAULT NULL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_telegram_id INTEGER NOT NULL,
                referred_telegram_id INTEGER UNIQUE NOT NULL,
                is_premium INTEGER DEFAULT 0,
                reward_amount REAL DEFAULT 0,
                rewarded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_telegram_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                details TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP DEFAULT NULL
            )
        """)

        # ====================================================
        # CATALOGS
        # ====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS catalogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER DEFAULT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (parent_id)
                REFERENCES catalogs(id)
            )
        """)

        # ====================================================
        # МИГРАЦИЯ CATALOGS
        #
        # Если база была создана старой версией,
        # добавляем parent_id.
        # Все старые каталоги автоматически становятся
        # главными каталогами (parent_id = NULL).
        # ====================================================

        cursor = await db.execute("""
            PRAGMA table_info(catalogs)
        """)

        catalog_columns = await cursor.fetchall()

        catalog_column_names = [
            column[1]
            for column in catalog_columns
        ]

        if "parent_id" not in catalog_column_names:

            await db.execute("""
                ALTER TABLE catalogs
                ADD COLUMN parent_id INTEGER DEFAULT NULL
            """)

        # ====================================================
        # PRODUCTS
        # ====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                catalog_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                image_file_id TEXT,
                price_rub REAL DEFAULT 0,
                price_usdt REAL DEFAULT 0,
                quantity INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (catalog_id)
                REFERENCES catalogs(id)
            )
        """)

        # ====================================================
        # ORDERS
        # ====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                order_code TEXT UNIQUE,

                user_id INTEGER NOT NULL,

                product_id INTEGER,

                payment_method TEXT NOT NULL,

                amount REAL NOT NULL,

                status TEXT DEFAULT 'waiting_payment',

                receipt_file_id TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                stars_quantity INTEGER DEFAULT NULL,

                stars_recipient TEXT DEFAULT NULL,

                 brawl_id TEXT DEFAULT NULL,

                FOREIGN KEY (user_id)
                REFERENCES users(id),

                FOREIGN KEY (product_id)
                REFERENCES products(id)
            )
        """)

        # ====================================================
        # МИГРАЦИЯ ORDERS
        # ====================================================

        cursor = await db.execute("""
            PRAGMA table_info(orders)
        """)

        columns = await cursor.fetchall()

        product_id_column = None

        for column in columns:

            if column[1] == "product_id":
                product_id_column = column
                break

        if product_id_column is not None:

            product_id_is_not_null = product_id_column[3] == 1

            if product_id_is_not_null:

                await db.execute("""
                    PRAGMA foreign_keys = OFF
                """)

                await db.execute("""
                    ALTER TABLE orders
                    RENAME TO orders_old
                """)

                await db.execute("""
                    CREATE TABLE orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,

                        order_code TEXT UNIQUE,

                        user_id INTEGER NOT NULL,

                        product_id INTEGER,

                        payment_method TEXT NOT NULL,

                        amount REAL NOT NULL,

                        status TEXT DEFAULT 'waiting_payment',

                        receipt_file_id TEXT,

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                        stars_quantity INTEGER DEFAULT NULL,

                stars_recipient TEXT DEFAULT NULL,

                 brawl_id TEXT DEFAULT NULL,

                        FOREIGN KEY (user_id)
                        REFERENCES users(id),

                        FOREIGN KEY (product_id)
                        REFERENCES products(id)
                    )
                """)

                await db.execute("""
                    INSERT INTO orders (
                        id,
                        user_id,
                        product_id,
                        payment_method,
                        amount,
                        status,
                        receipt_file_id,
                        created_at,
                        stars_quantity,
                        stars_recipient
                    )

                    SELECT
                        id,
                        user_id,
                        product_id,
                        payment_method,
                        amount,
                        status,
                        receipt_file_id,
                        created_at,
                        stars_quantity,
                        NULL

                    FROM orders_old
                """)

                await db.execute("""
                    DROP TABLE orders_old
                """)

                await db.execute("""
                    PRAGMA foreign_keys = ON
                """)

        # ====================================================
        # ПРОВЕРКА stars_quantity
        # ====================================================

        cursor = await db.execute("""
            PRAGMA table_info(orders)
        """)

        columns = await cursor.fetchall()

        column_names = [
            column[1]
            for column in columns
        ]

        if "stars_quantity" not in column_names:

            await db.execute("""
                ALTER TABLE orders
                ADD COLUMN stars_quantity INTEGER DEFAULT NULL
            """)


        # ====================================================
        # ПРОВЕРКА STARS RECIPIENT
        # ====================================================

        cursor = await db.execute("""
            PRAGMA table_info(orders)
        """)

        columns = await cursor.fetchall()
        column_names = [column[1] for column in columns]

        if "stars_recipient" not in column_names:
            await db.execute("""
                ALTER TABLE orders
                ADD COLUMN stars_recipient TEXT DEFAULT NULL
            """)

        # ====================================================
        # ПРОВЕРКА BRAWL ID
        # ====================================================

        cursor = await db.execute("""
            PRAGMA table_info(orders)
        """)

        columns = await cursor.fetchall()

        column_names = [
            column[1]
            for column in columns
        ]

        if "brawl_id" not in column_names:
            await db.execute("""
                ALTER TABLE orders
                ADD COLUMN brawl_id TEXT DEFAULT NULL
            """)

        # ====================================================
        # ПРОВЕРКА PUBLIC ORDER CODE
        # ====================================================

        cursor = await db.execute("PRAGMA table_info(orders)")
        columns = await cursor.fetchall()
        column_names = [column[1] for column in columns]

        if "order_code" not in column_names:
            await db.execute("ALTER TABLE orders ADD COLUMN order_code TEXT")

        # Заполняем публичные коды для старых заказов.
        cursor = await db.execute("SELECT id, order_code FROM orders ORDER BY id ASC")
        existing_rows = await cursor.fetchall()
        used_codes = {row[1] for row in existing_rows if row[1]}

        def make_order_code():
            alphabet = string.ascii_uppercase + string.digits
            return "".join(secrets.choice(alphabet) for _ in range(10))

        for order_id, order_code in existing_rows:
            if order_code:
                continue
            code = make_order_code()
            while code in used_codes:
                code = make_order_code()
            used_codes.add(code)
            await db.execute("UPDATE orders SET order_code = ? WHERE id = ?", (code, order_id))

        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_order_code ON orders(order_code)")

        # ====================================================
        # SETTINGS
        # ====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # ====================================================
        # DEFAULT SETTINGS
        # ====================================================

        await db.execute("""
            INSERT OR IGNORE INTO settings (
                key,
                value
            )
            VALUES (?, ?)
        """, (
            "rub_card",
            "2204 1201 4233 4453"
        ))

        # Старая версия хранила фотографию QR-кода СБП.
        # Полностью удаляем устаревшую настройку: теперь используется URL.
        await db.execute("DELETE FROM settings WHERE key = ?", ("sbp_qr_file_id",))

        await db.execute("""
            INSERT OR IGNORE INTO settings (
                key,
                value
            )
            VALUES (?, ?)
        """, (
            "sbp_payment_url",
            ""
        ))

        await db.execute("""
            INSERT OR IGNORE INTO settings (
                key,
                value
            )
            VALUES (?, ?)
        """, (
            "yoomoney_wallet",
            ""
        ))

        await db.execute("""
            INSERT OR IGNORE INTO settings (
                key,
                value
            )
            VALUES (?, ?)
        """, (
            "usdt_network",
            "TON"
        ))

        await db.execute("""
            INSERT OR IGNORE INTO settings (
                key,
                value
            )
            VALUES (?, ?)
        """, (
            "usdt_wallet",
            "UQBYTvsEibed_j0BRQJxkGDzhclsysKwuZlBm7LF3hE0vfHd"
        ))



        # ====================================================
        # CUSTOM EMOJI / PREMIUM EMOJI
        # Храним entities отдельно, чтобы существующие индексы
        # SELECT-ов и код бота не ломались.
        # ====================================================
        cursor = await db.execute("PRAGMA table_info(catalogs)")
        catalog_columns = [row[1] for row in await cursor.fetchall()]
        if "name_entities" not in catalog_columns:
            await db.execute("ALTER TABLE catalogs ADD COLUMN name_entities TEXT DEFAULT NULL")

        cursor = await db.execute("PRAGMA table_info(products)")
        product_columns = [row[1] for row in await cursor.fetchall()]
        if "name_entities" not in product_columns:
            await db.execute("ALTER TABLE products ADD COLUMN name_entities TEXT DEFAULT NULL")
        if "description_entities" not in product_columns:
            await db.execute("ALTER TABLE products ADD COLUMN description_entities TEXT DEFAULT NULL")
        if "quantity" not in product_columns:
            await db.execute("ALTER TABLE products ADD COLUMN quantity INTEGER DEFAULT 0")
        await db.commit()


# ============================================================
# USERS
# ============================================================

async def add_user(
    telegram_id: int,
    username: str | None,
    first_name: str | None
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            INSERT INTO users (
                telegram_id,
                username,
                first_name
            )

            VALUES (?, ?, ?)

            ON CONFLICT(telegram_id)
            DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (
            telegram_id,
            username,
            first_name
        ))

        await db.commit()


async def get_user_by_telegram_id(
    telegram_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                id,
                telegram_id,
                username,
                first_name

            FROM users

            WHERE telegram_id = ?
        """, (
            telegram_id,
        ))

        return await cursor.fetchone()


# ============================================================
# CATALOGS
# ============================================================

async def create_catalog(
    name: str,
    parent_id: int | None = None
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            INSERT INTO catalogs (
                name,
                parent_id
            )

            VALUES (?, ?)
        """, (
            name,
            parent_id,
        ))

        await db.commit()

        return cursor.lastrowid


async def get_catalogs(
    parent_id: int | None = None
):

    async with aiosqlite.connect(DB_NAME) as db:

        if parent_id is None:

            cursor = await db.execute("""
                SELECT
                    id,
                    name,
                    is_active

                FROM catalogs

                WHERE parent_id IS NULL

                ORDER BY id DESC
            """)

        else:

            cursor = await db.execute("""
                SELECT
                    id,
                    name,
                    is_active

                FROM catalogs

                WHERE parent_id = ?

                ORDER BY id DESC
            """, (
                parent_id,
            ))

        return await cursor.fetchall()


async def get_catalog(
    catalog_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                id,
                name,
                is_active

            FROM catalogs

            WHERE id = ?
        """, (
            catalog_id,
        ))

        return await cursor.fetchone()


async def get_catalog_parent_id(
    catalog_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                parent_id

            FROM catalogs

            WHERE id = ?
        """, (
            catalog_id,
        ))

        result = await cursor.fetchone()

        if result:
            return result[0]

        return None


async def get_catalog_children(
    catalog_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                id,
                name,
                is_active

            FROM catalogs

            WHERE parent_id = ?

            ORDER BY id DESC
        """, (
            catalog_id,
        ))

        return await cursor.fetchall()


async def has_catalog_children(
    catalog_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                1

            FROM catalogs

            WHERE parent_id = ?

            LIMIT 1
        """, (
            catalog_id,
        ))

        result = await cursor.fetchone()

        return result is not None


async def delete_catalog(
    catalog_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        async def delete_recursive(current_id: int):

            cursor = await db.execute("""
                SELECT id

                FROM catalogs

                WHERE parent_id = ?
            """, (
                current_id,
            ))

            children = await cursor.fetchall()

            for child in children:

                await delete_recursive(
                    child[0]
                )

            await db.execute("""
                DELETE FROM products

                WHERE catalog_id = ?
            """, (
                current_id,
            ))

            await db.execute("""
                DELETE FROM catalogs

                WHERE id = ?
            """, (
                current_id,
            ))

        await delete_recursive(
            catalog_id
        )

        await db.commit()


# ============================================================
# PRODUCTS
# ============================================================

async def create_product(
    catalog_id: int,
    name: str,
    description: str,
    image_file_id: str | None,
    price_rub: float,
    price_usdt: float,
    quantity: int = 0,
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            INSERT INTO products (
                catalog_id,
                name,
                description,
                image_file_id,
                price_rub,
                price_usdt,
                quantity
            )

            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            catalog_id,
            name,
            description,
            image_file_id,
            price_rub,
            price_usdt,
            int(quantity or 0)
        ))

        await db.commit()

        return cursor.lastrowid


async def get_products(
    catalog_id: int | None = None
):

    async with aiosqlite.connect(DB_NAME) as db:

        if catalog_id is None:

            cursor = await db.execute("""
                SELECT
                    products.id,
                    products.name,
                    products.description,
                    products.image_file_id,
                    products.price_rub,
                    products.price_usdt,
                    products.is_active,
                    catalogs.name,
                    products.quantity

                FROM products

                LEFT JOIN catalogs
                    ON products.catalog_id = catalogs.id

                ORDER BY products.id DESC
            """)

        else:

            cursor = await db.execute("""
                SELECT
                    products.id,
                    products.name,
                    products.description,
                    products.image_file_id,
                    products.price_rub,
                    products.price_usdt,
                    products.is_active,
                    catalogs.name,
                    products.quantity

                FROM products

                LEFT JOIN catalogs
                    ON products.catalog_id = catalogs.id

                WHERE products.catalog_id = ?

                ORDER BY products.id DESC
            """, (
                catalog_id,
            ))

        return await cursor.fetchall()


async def get_product(
    product_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                products.id,
                products.catalog_id,
                products.name,
                products.description,
                products.image_file_id,
                products.price_rub,
                products.price_usdt,
                products.is_active,
                catalogs.name,
                products.quantity

            FROM products

            LEFT JOIN catalogs
                ON products.catalog_id = catalogs.id

            WHERE products.id = ?
        """, (
            product_id,
        ))

        return await cursor.fetchone()


async def delete_product(
    product_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            DELETE FROM products

            WHERE id = ?
        """, (
            product_id,
        ))

        await db.commit()


async def toggle_product(
    product_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            UPDATE products

            SET is_active =
                CASE
                    WHEN is_active = 1 THEN 0
                    ELSE 1
                END

            WHERE id = ?
        """, (
            product_id,
        ))

        await db.commit()


# ============================================================
# SETTINGS
# ============================================================

async def get_setting(
    key: str
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT value

            FROM settings

            WHERE key = ?
        """, (
            key,
        ))

        result = await cursor.fetchone()

        if result:
            return result[0]

        return None


async def set_setting(
    key: str,
    value: str
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            INSERT INTO settings (
                key,
                value
            )

            VALUES (?, ?)

            ON CONFLICT(key)
            DO UPDATE SET
                value = excluded.value
        """, (
            key,
            value
        ))

        await db.commit()


# ============================================================
# ORDERS
# ============================================================

async def create_order(
    user_id: int,
    product_id: int | None,
    payment_method: str,
    amount: float,
    stars_quantity: int | None = None,
    brawl_id: str | None = None,
    stars_recipient: str | None = None
):

    async with aiosqlite.connect(DB_NAME) as db:

        alphabet = string.ascii_uppercase + string.digits

        while True:
            order_code = "".join(secrets.choice(alphabet) for _ in range(10))
            cursor = await db.execute(
                "SELECT 1 FROM orders WHERE order_code = ? LIMIT 1",
                (order_code,),
            )
            if await cursor.fetchone() is None:
                break

        cursor = await db.execute("""
            INSERT INTO orders (
                order_code,
                user_id,
                product_id,
                payment_method,
                amount,
                status,
                stars_quantity,
                brawl_id,
                stars_recipient
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_code,
            user_id,
            product_id,
            payment_method,
            amount,
            "waiting_payment",
            stars_quantity,
            brawl_id,
            stars_recipient
        ))

        await db.commit()

        return cursor.lastrowid


async def get_order_code(order_id: int):
    """Return the public random order code for an internal order id."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT order_code FROM orders WHERE id = ?",
            (order_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else str(order_id)


async def get_order(
    order_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                orders.id,
                orders.user_id,
                orders.product_id,
                orders.payment_method,
                orders.amount,
                orders.status,
                orders.receipt_file_id,
                orders.created_at,
                users.telegram_id,
                users.username,
                users.first_name,
                COALESCE(
                    products.name,
                    'Telegram Stars'
                ),
                orders.stars_quantity,
                orders.brawl_id,
                orders.stars_recipient,
                orders.order_code

            FROM orders

            JOIN users
                ON orders.user_id = users.id

            LEFT JOIN products
                ON orders.product_id = products.id

            WHERE orders.id = ?
        """, (
            order_id,
        ))

        return await cursor.fetchone()


async def add_receipt(
    order_id: int,
    receipt_file_id: str
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            UPDATE orders

            SET
                receipt_file_id = ?,
                status = 'waiting_review'

            WHERE id = ?
        """, (
            receipt_file_id,
            order_id
        ))

        await db.commit()


async def update_order_status(
    order_id: int,
    status: str
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            UPDATE orders

            SET status = ?

            WHERE id = ?
        """, (
            status,
            order_id
        ))

        await db.commit()


async def get_user_orders(
    user_id: int
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                orders.id,
                COALESCE(
                    products.name,
                    'Telegram Stars'
                ),
                orders.payment_method,
                orders.amount,
                orders.status,
                orders.created_at,
                orders.stars_quantity,
                 orders.brawl_id,
                orders.order_code

            FROM orders

            LEFT JOIN products
                ON orders.product_id = products.id

            WHERE orders.user_id = ?

            ORDER BY orders.id DESC
        """, (
            user_id,
        ))

        return await cursor.fetchall()


async def get_orders():

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT
                orders.id,
                users.telegram_id,
                users.username,
                COALESCE(
                    products.name,
                    'Telegram Stars'
                ),
                orders.payment_method,
                orders.amount,
                orders.status,
                orders.created_at,
                orders.stars_quantity,
                 orders.brawl_id,
                orders.order_code

            FROM orders

            JOIN users
                ON orders.user_id = users.id

            LEFT JOIN products
                ON orders.product_id = products.id

            ORDER BY orders.id DESC
        """)

        return await cursor.fetchall()

# ============================================================
# ROULETTE
# ============================================================

async def get_roulette_data(telegram_id: int):
    """Return (discount, last_spin) for a Telegram user."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT roulette_discount, roulette_last_spin FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return 0, None
        return int(row[0] or 0), row[1]


async def set_roulette_result(telegram_id: int, discount: int, spin_date: str):
    """Save the daily spin result and date."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE users
            SET roulette_discount = ?, roulette_last_spin = ?
            WHERE telegram_id = ?
            """,
            (int(discount), spin_date, telegram_id),
        )
        await db.commit()


async def consume_roulette_discount(telegram_id: int):
    """Consume the stored roulette discount after it is attached to a purchase."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET roulette_discount = 0 WHERE telegram_id = ?",
            (telegram_id,),
        )
        await db.commit()


# ============================================================
# REFERRAL SYSTEM
# ============================================================

REF_REWARD_RUB = 50.0
REF_MIN_WITHDRAW_RUB = 300.0


async def user_has_paid_order(telegram_id: int) -> bool:
    """True if the user has at least one order with status 'paid' (admin-confirmed)."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT 1
            FROM orders
            JOIN users ON orders.user_id = users.id
            WHERE users.telegram_id = ?
              AND orders.status = 'paid'
            LIMIT 1
            """,
            (telegram_id,),
        )
        row = await cursor.fetchone()
        return row is not None


async def get_referral_balance(telegram_id: int) -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT COALESCE(referral_balance, 0) FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        return float(row[0]) if row else 0.0


async def get_referral_stats(telegram_id: int) -> tuple[int, int]:
    """Всего приглашённых, из них с Premium (вознаграждённых)."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_telegram_id = ?",
            (telegram_id,),
        )
        total = int((await cursor.fetchone())[0])
        cursor = await db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_telegram_id = ? AND rewarded = 1",
            (telegram_id,),
        )
        rewarded = int((await cursor.fetchone())[0])
        return total, rewarded


async def process_referral_on_start(
    referred_telegram_id: int,
    referrer_telegram_id: int | None,
    is_premium: bool,
) -> tuple[bool, str]:
    """Привязка реферала и начисление 50₽ только за Telegram Premium.

    Возвращает (success_rewarded, message_for_logs).
    """
    if not referrer_telegram_id:
        return False, "no referrer"
    if referrer_telegram_id == referred_telegram_id:
        return False, "self-ref"

    async with aiosqlite.connect(DB_NAME) as db:
        # Реферер должен существовать
        cursor = await db.execute(
            "SELECT telegram_id FROM users WHERE telegram_id = ?",
            (referrer_telegram_id,),
        )
        if not await cursor.fetchone():
            return False, "referrer not found"

        # Уже был в базе до этого /start? referred_by уже стоит
        cursor = await db.execute(
            "SELECT referred_by, created_at FROM users WHERE telegram_id = ?",
            (referred_telegram_id,),
        )
        user_row = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT id, rewarded FROM referrals WHERE referred_telegram_id = ?",
            (referred_telegram_id,),
        )
        existing = await cursor.fetchone()
        if existing:
            return False, "already referred"

        # Нельзя рефералить самого себя / уже привязан
        if user_row and user_row[0]:
            return False, "already has referred_by"

        await db.execute(
            "UPDATE users SET referred_by = ? WHERE telegram_id = ? AND referred_by IS NULL",
            (referrer_telegram_id, referred_telegram_id),
        )

        reward = REF_REWARD_RUB if is_premium else 0.0
        rewarded = 1 if is_premium else 0

        await db.execute(
            """INSERT INTO referrals
               (referrer_telegram_id, referred_telegram_id, is_premium, reward_amount, rewarded)
               VALUES (?, ?, ?, ?, ?)""",
            (
                referrer_telegram_id,
                referred_telegram_id,
                1 if is_premium else 0,
                reward,
                rewarded,
            ),
        )

        if is_premium:
            await db.execute(
                """UPDATE users
                   SET referral_balance = COALESCE(referral_balance, 0) + ?
                   WHERE telegram_id = ?""",
                (REF_REWARD_RUB, referrer_telegram_id),
            )

        await db.commit()

    if is_premium:
        return True, f"rewarded {REF_REWARD_RUB} to {referrer_telegram_id}"
    return False, "registered without premium (no reward)"


async def create_withdrawal_request(
    telegram_id: int,
    amount: float,
    details: str,
) -> tuple[bool, str, int | None]:
    # Требуем хотя бы один подтверждённый заказ (status=paid)
    if not await user_has_paid_order(telegram_id):
        return False, "Для вывода нужен хотя бы один успешный заказ (подтверждённый администратором).", None

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT COALESCE(referral_balance, 0) FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        balance = float(row[0]) if row else 0.0

        if amount < REF_MIN_WITHDRAW_RUB:
            return False, f"Минимальная сумма вывода: {int(REF_MIN_WITHDRAW_RUB)} ₽", None
        if amount > balance + 1e-9:
            return False, f"Недостаточно средств. Баланс: {balance:.0f} ₽", None

        # Резервируем сумму (списываем сразу)
        await db.execute(
            """UPDATE users
               SET referral_balance = referral_balance - ?
               WHERE telegram_id = ? AND referral_balance >= ?""",
            (amount, telegram_id, amount),
        )
        cursor = await db.execute(
            """INSERT INTO withdrawal_requests
               (user_telegram_id, amount, details, status)
               VALUES (?, ?, ?, 'pending')""",
            (telegram_id, amount, details),
        )
        req_id = cursor.lastrowid
        await db.commit()
        return True, "ok", req_id


async def get_pending_withdrawals(limit: int = 20):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """SELECT id, user_telegram_id, amount, details, status, created_at
               FROM withdrawal_requests
               WHERE status = 'pending'
               ORDER BY id ASC LIMIT ?""",
            (limit,),
        )
        return await cursor.fetchall()


async def set_withdrawal_status(request_id: int, status: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """UPDATE withdrawal_requests
               SET status = ?, processed_at = CURRENT_TIMESTAMP
               WHERE id = ? AND status = 'pending'""",
            (status, request_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def refund_withdrawal(request_id: int) -> bool:
    """Отклонить заявку и вернуть деньги на баланс."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """SELECT user_telegram_id, amount, status
               FROM withdrawal_requests WHERE id = ?""",
            (request_id,),
        )
        row = await cursor.fetchone()
        if not row or row[2] != "pending":
            return False
        user_id, amount, _ = row
        await db.execute(
            """UPDATE withdrawal_requests
               SET status = 'rejected', processed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (request_id,),
        )
        await db.execute(
            """UPDATE users
               SET referral_balance = COALESCE(referral_balance, 0) + ?
               WHERE telegram_id = ?""",
            (amount, user_id),
        )
        await db.commit()
        return True


async def get_payout_details(telegram_id: int) -> str | None:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT payout_details FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if not row or not row[0]:
            return None
        value = str(row[0]).strip()
        return value or None


async def set_payout_details(telegram_id: int, details: str) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET payout_details = ? WHERE telegram_id = ?",
            (details.strip(), telegram_id),
        )
        await db.commit()

