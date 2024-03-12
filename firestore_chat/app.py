import dash_mantine_components as dmc
from dash import ALL, Dash, Input, page_container
from dash_auth import BasicAuth

from firestore_chat import ids
from firestore_chat.server import server


app = Dash(
    __name__,
    server=server,
    use_pages=True,
    # Pages will be reloaded when the socket connects
    routing_callback_inputs={"socket_ids": Input(ids.socket(ALL), "socketId")},
    suppress_callback_exceptions=True,
)
server.secret_key = "Test!"
app.layout = dmc.MantineProvider(
    dmc.Paper(
        page_container,
        radius=0,
        sx={"minHeight": "100vh"},
    ),
    theme={"colorScheme": "dark"},
    withCSSVariables=True,
)

BasicAuth(
    app,
    username_password_list={
        "Bob": "123",
        "Alice": "123",
        "Jack": "123",
        "Emily": "123",
    },
)


if __name__ == "__main__":
    app.run_server(debug=True)
