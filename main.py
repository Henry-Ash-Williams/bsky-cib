import dash
import pandas as pd
import uuid
import dash_cytoscape as cyto
from dash import Output, Input, State, html, dcc
import networkx as nx
from dotenv import dotenv_values
from atproto import AsyncClient
import atproto_client.models as models
import asyncio
import re
from collections import Counter
from account_ranking import get_account_data
from dash import dash_table


# Asynchronous function to get posts by tag
async def get_posts_by_tag(client, tag: str, limit=10):
    response = await client.app.bsky.feed.search_posts(
        params=models.AppBskyFeedSearchPosts.Params(q=tag, limit=limit, sort='top')
    )
    return response.posts


# Extract hashtags from posts
def extract_tags(posts):
    tags = []
    pattern = re.compile(r"\#\w+")
    for post in posts:
        text = post.record.text
        tags.extend(pattern.findall(text.lower()))  # More efficient tag extraction
    return tags


# Fetch tag data asynchronously
async def get_tag_data(client, tag: str, limit=10):
    posts = await get_posts_by_tag(client, tag, limit)
    tags = extract_tags(posts)

    # Parallel fetching posts for related tags
    tasks = [get_posts_by_tag(client, f"{t} {tag}", limit) for t in tags]
    results = await asyncio.gather(*tasks)

    return [(tag, extract_tags(posts)) for tag, posts in zip(tags, results)]


# Create a graph from tags and connections
async def make_graph(client, start_tag, limit, k=1):
    tags = await get_tag_data(client, start_tag, limit)
    all_seen_tags = Counter()

    for tag, others in tags:
        all_seen_tags.update(others)
    all_seen_tags.update([tag for tag, _ in tags])

    G = nx.Graph()

    for tag, others in tags:
        if all_seen_tags[tag] > 1:
            G.add_edge(start_tag, tag)  # Link start_tag to each tag if frequent enough
        for other in others:
            if all_seen_tags[other] > k and other != tag:
                G.add_edge(tag, other)  # Add edge for frequent co-occurring tags

    return G, all_seen_tags


# Prepare graph data and elements for Cytoscape
async def make_data(tag, limit, k):
    dotenv = dotenv_values(".env")

    client = AsyncClient()
    await client.login(dotenv["USERNAME"], dotenv["PASSWORD"])

    # Create graph and node sizes
    G, node_sizes = await make_graph(client, tag, limit, k)
    table = await get_account_data(client, tag, limit)
    pos = nx.spring_layout(G, iterations=50, k=0.8)

    elements = []
    for node in G.nodes():
        x, y = pos[node]
        elements.append(
            {
                "data": {"id": str(node), "label": f"{node}", "size": node_sizes[node]},
                "position": {"x": x, "y": y},
            }
        )

    # Add edges between nodes
    for edge in G.edges():
        elements.append({"data": {"source": str(edge[0]), "target": str(edge[1])}})

    return G, elements, table


def make_table(df):
    df = df.reset_index()
    table = dash_table.DataTable(
        data=df.to_dict("records"),
        page_size=20,
        id="table",
        style_table={"width": "100%", "height": "100%"},
    )
    return html.Div([
        table,
    ], id="table-container", style={"flex": "1", "overflow": "auto", "padding": "10px"})


def graph(elements):
    return html.Div(
        [
            cyto.Cytoscape(
                id="graph",
                elements=elements,
                layout={
                    "name": "cose",
                    "nodeRepulsion": 1000000,
                    "idealEdgeLength": 200,
                },
                stylesheet=[
                    {
                        "selector": "node",
                        "style": {
                            "width": "data(size)",
                            "height": "data(size)",
                            "background-color": "#007bff",
                            "label": "data(label)",
                            "text-valign": "center",
                            "color": "black",
                            "font-size": "mapData(zoom, 0.5, 2, 10px, 100px)",
                        },
                    },
                    {
                        "selector": "edge",
                        "style": {
                            "width": 2,
                            "line-color": "#aaa",
                        },
                    },
                ],
                style={"width": "100%", "height": "100%"}
            )
        ], 
        style={"flex": "1", "overflow": "hidden", "padding": "10px"}
    )


def query(k, default_tag):
    return (
        html.Div(
            [
                dcc.Input(
                    id="tag-input",
                    type="text",
                    placeholder="Enter tag(s)",
                    style={"width": "50%", "padding": "10px"},
                    value=default_tag
                ),
                # Date range picker
                dcc.DatePickerRange(
                    id="date-picker-range",
                    start_date_placeholder_text="Start Date",
                    end_date_placeholder_text="End Date",
                    calendar_orientation="horizontal",
                    style={"width": "30%", "padding": "10px"},
                ),
                # Submit button
                html.Button("Submit", id="submit-button", n_clicks=0),
                html.Br(),
                html.Br(),
                html.Div(
                    [
                        dcc.Slider(min=1, max=200, id="degree-slider", value=k),
                    ],
                    style={"width": "100%", "margin-bottom": "20px"},
                ),  # Add some margin for separation
            ],
            id="query",
        ),
    )


# Dash App
def main():
    app = dash.Dash(__name__)
    k = 5  # Initial slider value
    default_tag = "#germany"

    # Create the event loop and fetch initial graph data synchronously
    loop = asyncio.get_event_loop()
    G, elements, table = loop.run_until_complete(make_data(default_tag, 10, k))

    app.layout = html.Div(
        [
            query(k, default_tag)[0],
            html.Div(
                [
                    make_table(table),
                    graph(elements),
                ], 
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "width": "100vw",
                    "height": "80vh",
                    "overflow": "hidden",
                }
            )
        ]
    )

    # # Callback to highlight connected nodes when a node is tapped
    @app.callback(
        Output("graph", "stylesheet"),
        Input("graph", "tapNodeData"),
        prevent_initial_call=True,
    )
    def highlight_connected_nodes(node_data):
        if not node_data:
            return dash.no_update

        selected_node = node_data["id"]
        connected_nodes = {selected_node}

        # Find edges connected to the selected node
        for edge in G.edges():
            if selected_node in edge:
                connected_nodes.update(map(str, edge))

        # New stylesheet with highlighted connected nodes
        new_styles = [
            {
                "selector": f"node[id = '{n}']",
                "style": {"background-color": "#FF8400", "color": "black"},
            }
            for n in connected_nodes
        ] + [
            {
                "selector": f"edge[source='{edge[0]}'][target='{edge[1]}'], edge[source='{edge[1]}'][target='{edge[0]}']",
                "style": {"line-color": "#555", "width": 4},
            }
            for edge in G.edges()
            if str(edge[0]) in connected_nodes and str(edge[1]) in connected_nodes
        ]

        return [
            {
                "selector": "node",
                "style": {
                    "width": "data(size)",
                    "height": "data(size)",
                    "background-color": "#007bff",
                    "label": "data(label)",
                    "text-valign": "center",
                    "color": "black",
                    "font-size": "10px",
                },
            },
            {"selector": "edge", "style": {"width": 2, "line-color": "#aaa"}},
        ] + new_styles

    # Synchronous wrapper for async function in callback
    @app.callback(
        Output("graph", "elements"),
        Output("table-container", "children"),
        Input("degree-slider", "value"),
        Input("submit-button", "n_clicks"),
        State("tag-input", "value"),
    )
    def update_graph(k, n_clicks, tag=default_tag):
        global G
        """Update graph elements when the slider value changes."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)  # Set the new loop for this callback thread
        print(k, n_clicks, tag)
        Gi, elements, table = loop.run_until_complete(make_data(tag, 10, k))
        loop.close()  # Close the loop when done
        G = Gi

        return elements, [make_table(table)]

    app.run_server(debug=True)


if __name__ == "__main__":
    main()
