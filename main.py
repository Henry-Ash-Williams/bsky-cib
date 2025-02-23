from collections import Counter
import dash
import dash_cytoscape as cyto
from dash import dcc, html
import networkx as nx

from dotenv import dotenv_values 
from atproto import AsyncClient 
import atproto_client.models as models

import asyncio
import re

async def get_posts_by_tag(client, tag: str, limit=10):
    response = await client.app.bsky.feed.search_posts(
        params=models.AppBskyFeedSearchPosts.Params(
            q=tag,  
            limit=limit
        )
    )

    return response.posts

def extract_tags(posts):
    tags = []
    pattern = re.compile('\#\w+')
    
    for post in posts: 
        text = post.record.text
        [tags.append(tag) for tag in pattern.findall(text.lower())]

    return tags

async def get_tag_data(client, tag: str, limit=10):
    posts = await get_posts_by_tag(client, tag, limit)
    tags = extract_tags(posts) 

    tasks = [get_posts_by_tag(client, f"{t} {tag}", limit) for t in tags]
    results = await asyncio.gather(*tasks)

    return [(tag, extract_tags(posts)) for tag, posts in zip(tags, results)]

async def make_graph(client, start_tag, limit):
    tags = await get_tag_data(client, start_tag, limit)
    all_seen_tags = Counter() 

    for tag, others in tags: 
        all_seen_tags.update(others)
    all_seen_tags.update([tag for tag, _ in tags])

    G = nx.Graph()

    for tag, others in tags: 
        if all_seen_tags[tag] > 1: 
            G.add_edge(start_tag, tag) 

        [G.add_edge(tag, other) for other in others if all_seen_tags[other] > 5 and other != tag]

    return G, all_seen_tags

async def main():
    dotenv = dotenv_values('.env')

    client = AsyncClient() 
    await client.login(dotenv['USERNAME'], dotenv['PASSWORD'])

    # Create a sample graph
    G, node_sizes = await make_graph(client, "#germany", 10)
    pos = nx.spring_layout(G, iterations=100, k=0.8)

    elements = []
    for node in G.nodes():
        x, y = pos[node]

        elements.append({
            "data": {"id": str(node), "label": f"{node}", "size": node_sizes[node]},
            "position": {"x": x * 500, "y": y * 500}
        })

    for edge in G.edges():
        elements.append({"data": {"source": str(edge[0]), "target": str(edge[1])}})

    app = dash.Dash(__name__)

    app.layout = html.Div([
        cyto.Cytoscape(
            id="graph",
            elements=elements,
            style={"width": "100%", "height": "600px"},
            layout={"name": "cose", "nodeRepulsion": 1000000, "idealEdgeLength": 200},  # Force-directed layout with collision handling
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
                        "font-size": "10px"
                    }
                },
                {
                    "selector": "edge",
                    "style": {
                        "width": 2,
                        "line-color": "#aaa"
                    }
                }
            ]
        )
    ])
    app.run_server(debug=True)

if __name__ == "__main__":
    asyncio.run(main())