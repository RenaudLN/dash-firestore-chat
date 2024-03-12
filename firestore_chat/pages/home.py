import dash_mantine_components as dmc
from dash import (
    Input,
    Output,
    State,
    callback,
    clientside_callback,
    html,
    register_page,
    no_update,
)
from dash.dash import _ID_LOCATION
from flask import session

from firestore_chat import ids


register_page(__name__, path="/")


def layout(**_kwargs):
    """Home page layout."""
    if "user" not in session:
        return dmc.Text("Something went wrong")

    return dmc.Container(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.Title(f"Welcome {session['user']['email']}", order=2),
                        dmc.Button("Logout", id=ids.signout, ml="auto", compact=True),
                    ],
                    mb="lg",
                ),
                dmc.Title("Create or join a room", order=4),
                dmc.TextInput(
                    id=ids.create_room,
                    label="Room name",
                    value=session.get("room_name"),
                ),
                html.Div(dmc.Button("Join", id=ids.join)),
                html.Div(id=ids.home_dummy),
            ]
        ),
        py="3rem",
    )


@callback(
    Output(_ID_LOCATION, "pathname", allow_duplicate=True),
    Input(ids.join, "n_clicks"),
    State(ids.create_room, "value"),
    prevent_initial_call=True,
)
def join_room(trigger, room_name):
    """Redirect to selected room."""
    if not room_name or not trigger:
        return no_update
    return f"/chat/{room_name}"


@callback(
    Output(ids.home_dummy, "data-sessionClear"),
    Input(ids.signout, "n_clicks"),
    prevent_initial_call=True,
)
def signout(_n):
    """Clear the session on signout"""
    session.clear()
    return no_update


# Hack to signout of basic auth
clientside_callback(
    """(n) => {
        if (!n) return dash_clientside.no_udpate
        const request = new XMLHttpRequest();
        request.open("get", "/logout", false, "false", "false");
        request.send();
        window.location.replace("/");
        return dash_clientside.no_udpate
    }""",
    Output(ids.home_dummy, "data-logout"),
    Input(ids.signout, "n_clicks"),
    prevent_initial_call=True,
)
