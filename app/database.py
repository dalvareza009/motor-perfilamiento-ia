import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

def show_clientes_limpios():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            SELECT *
            FROM public.clientes_limpios
            LIMIT 1;
        """)

        columns_info = cursor.description
        if columns_info is None:
            print("La consulta no devolvió columnas.")
            return

        columns = [desc[0] for desc in columns_info]
        row = cursor.fetchone()

        print("\nColumnas de clientes_limpios:")
        for column in columns:
            print(f"- {column}")

        print("\nPrimer registro:")
        if row:
            for column, value in zip(columns, row):
                print(f"{column}: {value}")

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    show_clientes_limpios()