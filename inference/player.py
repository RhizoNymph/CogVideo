import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.wsgi import WSGIMiddleware
from starlette.responses import HTMLResponse
import dash
from dash import html, dcc, Input, Output, State, clientside_callback
import dash_bootstrap_components as dbc

# Initialize FastAPI
app = FastAPI()

# Initialize Dash with a dark theme
dash_app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], requests_pathname_prefix="/dash/")

# Define the directory where your video folders are located
VIDEO_DIR = './batches/'

def get_playlists() -> List[str]:
    return sorted([folder for folder in os.listdir(VIDEO_DIR) if os.path.isdir(os.path.join(VIDEO_DIR, folder))])

def get_videos(playlist: str) -> List[str]:
    playlist_dir = os.path.join(VIDEO_DIR, playlist)
    return sorted([video for video in os.listdir(playlist_dir) if video.endswith(('.mp4', '.avi', '.mov'))])

# Dash app layout
dash_app.layout = dbc.Container([
    html.H1("Video Playlist App", className="my-4"),
    dbc.Row([
        dbc.Col([
            dcc.Dropdown(
                id='playlist-dropdown',
                options=[{'label': playlist, 'value': playlist} for playlist in get_playlists()],
                placeholder="Select a playlist",
                className="mb-3"
            ),
            html.Div(id='video-list')
        ], width=3),
        dbc.Col([
            html.Video(id='video-player', controls=True, autoPlay=True, style={'width': '100%'}),
            dbc.Button("Next Video", id='next-video-button', n_clicks=0, className="mt-3")
        ], width=9)
    ]),
    dcc.Store(id='current-playlist'),
    dcc.Store(id='current-video-index')
], fluid=True, className="p-5")

@dash_app.callback(
    Output('video-list', 'children'),
    Output('current-playlist', 'data'),
    Input('playlist-dropdown', 'value')
)
def update_video_list(selected_playlist):
    if not selected_playlist:
        return [], None
    videos = get_videos(selected_playlist)
    return [html.Li(video, className="list-group-item") for video in videos], selected_playlist

@dash_app.callback(
    Output('video-player', 'src'),
    Output('current-video-index', 'data'),
    Input('playlist-dropdown', 'value'),
    Input('next-video-button', 'n_clicks'),
    Input('video-player', 'ended'),
    State('current-playlist', 'data'),
    State('current-video-index', 'data')
)
def update_video_player(selected_playlist, n_clicks, video_ended, current_playlist, current_index):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'playlist-dropdown' and selected_playlist:
        videos = get_videos(selected_playlist)
        if videos:
            return f"/videos/{selected_playlist}/{videos[0]}", 0
    elif (trigger_id in ['next-video-button', 'video-player']) and current_playlist:
        videos = get_videos(current_playlist)
        if current_index is None:
            current_index = 0
        else:
            current_index = (current_index + 1) % len(videos)
        return f"/videos/{current_playlist}/{videos[current_index]}", current_index

    return dash.no_update, dash.no_update

# Client-side callback to handle video ended event
clientside_callback(
    """
    function(ended) {
        if (ended) {
            document.getElementById('next-video-button').click();
        }
    }
    """,
    Output('video-player', 'ended'),
    Input('video-player', 'ended')
)

# FastAPI routes
@app.get("/videos/{playlist}/{video}")
async def get_video(playlist: str, video: str):
    video_path = os.path.join(VIDEO_DIR, playlist, video)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(video_path)

# Mount Dash app
app.mount("/dash", WSGIMiddleware(dash_app.server))

@app.get("/")
async def read_root():
    return HTMLResponse("""
        <html>
            <head>
                <title>Video Playlist App</title>
                <style>
                    body {
                        background-color: #222;
                        color: #fff;
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .container {
                        text-align: center;
                    }
                    h1 { color: #0d6efd; }
                    a { color: #0d6efd; text-decoration: none; }
                    a:hover { text-decoration: underline; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Welcome to the Video Playlist App</h1>
                    <p>Click <a href="/dash/">here</a> to access the Dash application.</p>
                </div>
            </body>
        </html>
    """)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
