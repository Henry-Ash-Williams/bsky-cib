import atproto_client.models as models
import asyncio
import pandas as pd
from dateutil.parser import isoparse


async def get_account_data(client, tag, limit=10):
    async def make_metrics(client, author, posts):
        metrics = {}
        metrics["Followers"] = len((await client.get_followers(author)).followers)
        metrics["Following"] = len((await client.get_follows(author)).follows)
        metrics["Number of posts"] = len(posts)
        metrics["Total Likes"] = sum([post.like_count for post in posts])
        metrics["Total Replies"] = sum([post.reply_count for post in posts])
        metrics["Total Quotes"] = sum([post.quote_count for post in posts])
        metrics["Age at First Post"] = min( [isoparse(post.record.created_at) for post in posts]) - isoparse(posts[0].author.created_at)
        metrics["Total Engagements"] = (
            metrics["Total Likes"] + metrics["Total Replies"] + metrics["Total Quotes"]
        )
        return author, metrics

    response = await client.app.bsky.feed.search_posts(
        params=models.AppBskyFeedSearchPosts.Params(q=tag, limit=limit, sort="top")
    )

    authors = set([post.author.handle for post in response.posts])
    posts_by_author = {
        author: [post for post in response.posts if post.author.handle == author]
        for author in authors
    }
    tasks = [
        make_metrics(client, author, posts) for author, posts in posts_by_author.items()
    ]
    results = await asyncio.gather(*tasks)
    df = pd.DataFrame(dict(results)).transpose()
    df["Engagement Score"] = (
        (df["Total Engagements"] / df["Number of posts"]) * df["Followers"]
    ) / [age.seconds for age in df["Age at First Post"]]
    df['Age at First Post'] = [str(age) for age in df["Age at First Post"]]
    df = df[['Engagement Score', 'Total Engagements', 'Followers', 'Following', 'Total Likes', 'Total Replies', 'Total Quotes', 'Age at First Post']]
    return df.sort_values(by=["Engagement Score"], ascending=False)
