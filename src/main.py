import flet as ft

from hb.app import App


async def main(page: ft.Page):
    app = App(page)
    await app.start()


if __name__ == "__main__":
    ft.run(main)
