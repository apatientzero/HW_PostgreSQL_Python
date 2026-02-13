import psycopg2
from psycopg2 import sql


def create_db(conn):
    """Client and phone"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client (
                id SERIAL PRIMARY KEY,
                first_name VARCHAR(50) NOT NULL,
                last_name VARCHAR(50) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS phone (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
                phone VARCHAR(20) NOT NULL
            );
        """)
        conn.commit()


def add_client(conn, first_name, last_name, email, phones=None):
    """Add new client. phones — список строк (может быть None)"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO client (first_name, last_name, email)
            VALUES (%s, %s, %s) RETURNING id;
        """, (first_name, last_name, email))
        client_id = cur.fetchone()[0]

        if phones:
            for phone in phones:
                add_phone(conn, client_id, phone)
        conn.commit()
        return client_id


def add_phone(conn, client_id, phone):
    """Add a phone number for an existing customer"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO phone (client_id, phone)
            VALUES (%s, %s);
        """, (client_id, phone))
        conn.commit()


def change_client(conn, client_id, first_name=None, last_name=None, email=None, phones=None):
    """Modifies the client's data"""
    with conn.cursor() as cur:
        # Обновляем основные поля, если они заданы
        fields = []
        values = []
        if first_name is not None:
            fields.append("first_name = %s")
            values.append(first_name)
        if last_name is not None:
            fields.append("last_name = %s")
            values.append(last_name)
        if email is not None:
            fields.append("email = %s")
            values.append(email)

        if fields:
            query = sql.SQL("UPDATE client SET {} WHERE id = %s").format(
                sql.SQL(', ').join(sql.SQL(f) for f in fields)
            )
            cur.execute(query, values + [client_id])

        # Если передан phones — удаляем все старые и добавляем новые
        if phones is not None:
            cur.execute("DELETE FROM phone WHERE client_id = %s", (client_id,))
            for phone in phones:
                add_phone(conn, client_id, phone)

        conn.commit()


def delete_phone(conn, client_id, phone):
    """Delete a specific phone number from the client"""
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM phone
            WHERE client_id = %s AND phone = %s;
        """, (client_id, phone))
        conn.commit()


def delete_client(conn, client_id):
    """Delete the client (and all his phones automatically due to ON DELETE CASCADE)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM client WHERE id = %s;", (client_id,))
        conn.commit()


def find_client(conn, first_name=None, last_name=None, email=None, phone=None):
    """Searche for a client by any of the parameters"""
    with conn.cursor() as cur:
        # Начинаем с запроса к client
        query = """
            SELECT c.id, c.first_name, c.last_name, c.email
            FROM client c
        """
        conditions = []
        params = []

        if first_name:
            conditions.append("c.first_name = %s")
            params.append(first_name)
        if last_name:
            conditions.append("c.last_name = %s")
            params.append(last_name)
        if email:
            conditions.append("c.email = %s")
            params.append(email)
        if phone:
            # Если ищем по телефону — нужно JOIN с phone
            query += " JOIN phone p ON c.id = p.client_id"
            conditions.append("p.phone = %s")
            params.append(phone)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY c.id;"

        cur.execute(query, params)
        clients = cur.fetchall()

        # Теперь получим телефоны для каждого найденного клиента
        result = []
        for client in clients:
            client_id = client[0]
            cur.execute("SELECT phone FROM phone WHERE client_id = %s;", (client_id,))
            phones = [row[0] for row in cur.fetchall()]
            result.append((*client, phones))

        return result


# --- if __name__ == "__main__":---
if __name__ == "__main__":
    # Подключение
    with psycopg2.connect(database="clients_db", user="postgres", password="postgres") as conn:
        create_db(conn)
        print("База данных создана")

        # 1. Добавим клиентов
        id1 = add_client(conn, "Mike", "Tyson", "mike@example.com", ["+79001111111", "+79002222222"])
        id2 = add_client(conn, "Nina", "Dobrev", "nina@example.com", ["+79003333333"])
        id3 = add_client(conn, "Jessica", "Alba", "jessica@example.com")  # без телефона
        print(f"Клиенты добавлены: id1={id1}, id2={id2}, id3={id3}")

        # 2. Добавим телефон Jessica
        add_phone(conn, id3, "+79004444444")
        print("Телефон добавлен Jessica")

        # 3. Изменим данные Nina
        change_client(conn, id1, first_name="Nina S.", phones=["+79005555555"])
        print("Данные Nina изменены")

        # 4. Удалим один телефон Mike
        delete_phone(conn, id2, "+79003333333")
        print("Телефон Mike удалён")

        # 5. Поиск
        print("\nПоиск по имени 'Mike Н.':")
        print(find_client(conn, first_name="Mike W."))

        print("\nПоиск по телефону '+79004444444':")
        print(find_client(conn, phone="+79004444444"))

        print("\nПоиск по email 'nina@example.com':")
        print(find_client(conn, email="nina@example.com"))

        # 6. Удалим клиента
        delete_client(conn, id2)
        print("\nКлиент Mike удалён")

        print("\nВсе оставшиеся клиенты:")
        all_clients = find_client(conn)
        for c in all_clients:
            print(c)


    print("\nРабота завершена")

