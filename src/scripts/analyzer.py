"""
This script performs exploratory data analysis on a dataset of posts,
focusing on topics, authors, and content characteristics.  It loads post
data from a JSON file, preprocesses it, and then generates various
visualizations and statistical summaries.

The script defines several functions:

- `reduce_duplicated_post(posts)`: Removes duplicate posts based on title.
- `construct_dataframe(posts)`: Creates a Pandas DataFrame from a list of Post objects.
- `analyze_topic(df)`: Analyzes the distribution of topics, including popularity and associated tags.
- `analyze_author(df)`: Analyzes author-related attributes, such as follower count and topic diversity.
- `analyze_content(df)`: Analyzes content characteristics like tags, post types, sentiment, and length.
- `main()`:  The main function that orchestrates the data loading, preprocessing, and analysis.

The script uses libraries such as pandas, matplotlib, seaborn, and collections.
It assumes the existence of a `constants` module defining file paths and
a `core.parser` module with a function to load posts from JSON.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter


import constants
from core.parser import PostDataIO


def reduce_duplicated_post(posts):
    seen_titles = set()
    unique_posts = []

    for post in posts:
        if post.title not in seen_titles:
            unique_posts.append(post)
            seen_titles.add(post.title)

    return unique_posts

def construct_dataframe(posts):
    data = []
    for post in posts:
        post_data = {
            'title': post.title,
            'like_count': post.like_count,
            'topic': post.topic,
            'author_followers': post.author.follower_num if post.author else None,
            'author_following': post.author.following_num if post.author else None,
            'post_type': post.post_type.name,  # Use .name for string representation
            'sentiment_type': post.sentiment_type.name,
            'content_length_type': post.content_length_type.name,
            'is_hotspot': post.is_hotspot,
            'is_creative': post.is_creative,
            'tags': ','.join(post.tags),  # Join tags into a single string
        }
        data.append(post_data)

    df = pd.DataFrame(data)
    plt.rcParams['font.sans-serif'] = ['Songti SC']

    return df

def analyze_topic(df):
    ## a. Most popular topics:
    topic_counts = df['topic'].value_counts()
    print("\nMost popular topics:\n", topic_counts)

    # Display more information about the topics
    print("\nTop 10 most popular topics:")
    for topic, count in topic_counts.head(10).items():
        print(f"- {topic}: {count} posts")

    print("\nAll topics and their counts:")
    for topic, count in topic_counts.items():
        print(f"- {topic}: {count} posts")

    topic_counts.head(10).plot(kind='bar', title='Top 10 Topics')  # Visualize top 10
    plt.show()

    ## b. the average like numbers per post in the different topics
    print("\n--- Topic Popularity (by Average Likes) ---")
    topic_avg_likes = df.groupby('topic')['like_count'].mean().sort_values(ascending=False)
    print("\nAverage like numbers per post in different topics (Top 20):\n", topic_avg_likes.head(20))

    # Visualize top N topics by average likes
    plt.figure(figsize=(12, 6))
    topic_avg_likes.head(20).plot(kind='bar', title='Top 20 Topics by Average Like Count')
    plt.xlabel('Topic')
    plt.ylabel('Average Like Count')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()


    ## c. the tags for the top 20 most popular topics
    print("\n--- Tag Analysis for Top 20 Topics ---")

    # First, determine the top 20 topics based on post count if not already done
    topic_counts = df['topic'].value_counts()
    top_20_topic_names = topic_counts.head(20).index.tolist()
    top_20_df = df[df['topic'].isin(top_20_topic_names)].copy() # Create a filtered DataFrame

    def get_top_tags(tag_series, n=10):
        """Helper function to get top N tags from a series of comma-separated tag strings."""
        all_tags = []
        for tags_str in tag_series.dropna(): # Drop rows where tags might be NaN/None
             # Split, strip whitespace, and filter out empty strings
            tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            all_tags.extend(tags_list)
        if not all_tags:
            return [] # Return empty list if no valid tags found
        return Counter(all_tags).most_common(n)

    # Apply the function to each topic group within the top 20 topics
    # Ensure 'tags' column exists and handle potential errors if it doesn't
    if 'tags' in top_20_df.columns:
        top_topic_tags = top_20_df.groupby('topic')['tags'].apply(get_top_tags)
        print("\nTop 5 Tags for the Top 20 Most Popular Topics (by post count):\n")
        # Ensure the output is aligned with the actual top 20 topics based on count
        for topic in top_20_topic_names:
             if topic in top_topic_tags.index:
                 tags = top_topic_tags[topic]
                 tag_str = ", ".join([f"{tag} ({count})" for tag, count in tags]) if tags else "No prominent tags"
                 print(f"- {topic}: {tag_str}")
             else:
                 # This case might occur if a topic had posts but no tags in any of them
                 print(f"- {topic}: No tags found")
    else:
        print("Error: 'tags' column not found in the DataFrame.")

    ## d. the distribution of post type in the top 20 most popular topics
    print("\n--- Post Type Distribution in Top 20 Topics ---")

    # Reuse top 20 topics identification if already done, otherwise calculate
    topic_counts = df['topic'].value_counts()
    top_20_topic_names = topic_counts.head(20).index.tolist()
    top_20_df = df[df['topic'].isin(top_20_topic_names)].copy()

    # Handle potential missing 'post_type' column or NaN values if necessary
    if 'post_type' in top_20_df.columns and not top_20_df['post_type'].isnull().all():
        # Use crosstab for a clear view of counts or proportions
        post_type_dist = pd.crosstab(top_20_df['topic'], top_20_df['post_type'])
        print("\nCounts:\n", post_type_dist) # Optional: print counts

        # Calculate proportions within each topic (row-wise normalization)
        # Ensure the index of the result matches the order of top_20_topic_names for consistency
        post_type_dist_prop = pd.crosstab(top_20_df['topic'], top_20_df['post_type'], normalize='index').reindex(top_20_topic_names)
        print("\nProportions:\n", post_type_dist_prop)

        # Visualize proportions using a stacked bar chart
        if not post_type_dist_prop.empty:
            plt.figure(figsize=(14, 8))
            # Use the proportion DataFrame directly for plotting
            post_type_dist_prop.plot(kind='bar', stacked=True, ax=plt.gca()) # Use current axis
            plt.title('Post Type Distribution within Top 20 Topics')
            plt.xlabel('Topic')
            plt.ylabel('Proportion of Post Types')
            plt.xticks(rotation=45, ha='right')
            plt.legend(title='Post Type', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            plt.show()
        else:
            print("No data to visualize for post type distribution.")
    else:
        print("Could not perform post type distribution analysis. Check 'post_type' column and data.")

    # e. the distribution of post length in the top 20 most popular topics
    print("\n--- Content Length Distribution in Top 20 Topics ---")

    # Assuming top_20_topic_names and top_20_df are available from section (d)
    # If not, recalculate:
    topic_counts = df['topic'].value_counts()
    top_20_topic_names = topic_counts.head(20).index.tolist()
    top_20_df = df[df['topic'].isin(top_20_topic_names)].copy()

    # Handle potential missing 'content_length_type' column or NaN values
    if 'content_length_type' in top_20_df.columns and not top_20_df['content_length_type'].isnull().all():
        # Define the desired order for content length types
        content_length_order = ['SHORT', 'MEDIUM', 'LONG', 'LONGER'] # Adjust if your actual values differ

        # Ensure 'content_length_type' is categorical with the correct order
        top_20_df['content_length_type'] = pd.Categorical(
            top_20_df['content_length_type'],
            categories=content_length_order,
            ordered=True
        )

        # Use crosstab for proportions, normalized by topic (index)
        content_length_dist_prop = pd.crosstab(
            top_20_df['topic'],
            top_20_df['content_length_type'],
            normalize='index',
            dropna=False # Include topics even if they only have NaN length types (though ideally handled earlier)
        ).reindex(top_20_topic_names) # Maintain the order of top topics

        # Ensure all expected columns are present, fill missing with 0
        content_length_dist_prop = content_length_dist_prop.reindex(columns=content_length_order, fill_value=0)


        print("\nProportions:\n", content_length_dist_prop)

        # Visualize proportions using a stacked bar chart
        if not content_length_dist_prop.empty:
            plt.figure(figsize=(14, 8))
            content_length_dist_prop.plot(kind='bar', stacked=True, ax=plt.gca())
            plt.title('Content Length Distribution within Top 20 Topics')
            plt.xlabel('Topic')
            plt.ylabel('Proportion of Content Length Types')
            plt.xticks(rotation=45, ha='right')
            plt.legend(title='Content Length', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            plt.show()
        else:
            print("No data to visualize for content length distribution.")
    else:
        print("Could not perform content length distribution analysis. Check 'content_length_type' column and data.")


    ## f. the distribution of sentiment in the top 20 most popular topics
    print("\n--- Sentiment Distribution in Top 20 Topics ---")

    # Ensure top_20_topic_names and top_20_df are available
    # Recalculate if necessary to ensure this section runs independently
    # Note: This recalculation assumes 'top 20' is based on post count.
    topic_counts = df['topic'].value_counts()
    top_20_topic_names = topic_counts.head(20).index.tolist()
    top_20_df = df[df['topic'].isin(top_20_topic_names)].copy()

    # Handle potential missing 'sentiment_type' column or NaN values
    if 'sentiment_type' in top_20_df.columns and not top_20_df['sentiment_type'].isnull().all():
        # Define the desired order for sentiment types (adjust if your actual values differ)
        # Example: ['NEGATIVE', 'NEUTRAL', 'POSITIVE']. Check your actual enum names.
        # Assuming SentimentType enum has .name attribute giving strings like 'POSITIVE' etc.
        # Let's dynamically get possible values if possible, or define explicitly
        try:
            # Attempt to get names from the enum if it's accessible and consistent
            # This requires knowing the Enum definition (e.g., constants.SentimentType)
            # If constants.SentimentType is not directly available here, define manually:
             sentiment_order = ['NEGATIVE', 'NEUTRAL', 'POSITIVE'] # Adjust if needed based on your SentimentType enum
            # from sentiment_analysis import SentimentType # Or wherever it's defined
            # sentiment_order = [s.name for s in SentimentType]
        except NameError:
             # Fallback to a predefined list if the enum isn't easily accessible
             sentiment_order = ['NEGATIVE', 'NEUTRAL', 'POSITIVE'] # Adjust if needed

        # Ensure 'sentiment_type' is categorical with the correct order
        # This helps in consistent plotting and interpretation
        top_20_df['sentiment_type'] = pd.Categorical(
            top_20_df['sentiment_type'],
            categories=sentiment_order,
            ordered=True # Order matters for interpretation if defined
        )

        # Use crosstab for proportions, normalized by topic (index)
        sentiment_dist_prop = pd.crosstab(
            top_20_df['topic'],
            top_20_df['sentiment_type'],
            normalize='index',
            dropna=False # Keep topics even if they lack certain sentiment types
        ).reindex(top_20_topic_names) # Maintain the order of top topics

        # Ensure all expected sentiment columns are present, fill missing with 0
        sentiment_dist_prop = sentiment_dist_prop.reindex(columns=sentiment_order, fill_value=0)

        print("\nSentiment Proportions within Top 20 Topics:\n", sentiment_dist_prop)

        # Visualize proportions using a stacked bar chart
        if not sentiment_dist_prop.empty:
            plt.figure(figsize=(14, 8))
            # Plot the reindexed and filled dataframe for correct order and all categories
            sentiment_dist_prop.plot(kind='bar', stacked=True, ax=plt.gca())
            plt.title('Sentiment Distribution within Top 20 Topics')
            plt.xlabel('Topic')
            plt.ylabel('Proportion of Sentiment Types')
            plt.xticks(rotation=45, ha='right')
            plt.legend(title='Sentiment Type', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            plt.show()
        else:
            print("No data to visualize for sentiment distribution.")
    else:
        print("Could not perform sentiment distribution analysis. Check 'sentiment_type' column and data.")

def analyze_author(df):
    ####################################################
    # A. draw author's follower number distribution
    ####################################################
    print("\n--- Analyzing Author Follower Distribution ---")

    # Filter out None values if present
    follower_data = df['author_followers'].dropna()

    # Basic statistics about follower counts
    print("\nStatistics of author follower counts:")
    print(follower_data.describe())

    # Add a log scale version to better see the distribution's tail
    plt.figure(figsize=(12, 6))
    sns.histplot(follower_data, kde=True, bins=30, log_scale=True)
    plt.title('Distribution of Author Follower Counts (Log Scale)')
    plt.xlabel('Number of Followers (Log Scale)')
    plt.ylabel('Frequency')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()

    # Group the follower number into bins and draw pie chart
    print("\n--- Follower Count Distribution (Binned) ---")

    # Define meaningful follower count bins
    bins = [0, 50, 100, 200, 500, 1000, 5000, 10000, float('inf')]
    labels = ['<50', '50-100', '100-200', '200-500', '500-1K', '1K-5K', '5K-10K', '10K+']

    # Create a new column with binned follower counts
    follower_groups = pd.cut(df['author_followers'].dropna(),
                             bins=bins,
                             labels=labels,
                             right=False)

    # Count the number of authors in each follower group
    follower_group_counts = follower_groups.value_counts().sort_index()

    # Display the counts
    print("\nFollower count distribution:")
    for group, count in follower_group_counts.items():
        print(f"- {group}: {count} authors ({count/len(follower_groups)*100:.1f}%)")

    # Create a pie chart to visualize the distribution
    plt.figure(figsize=(10, 8))
    follower_group_counts.plot(kind='pie',
                             autopct='%1.1f%%',
                             startangle=90,
                             shadow=False,
                             explode=[0.05] * len(labels),  # Slight separation for all slices
                             colors=sns.color_palette("pastel"))
    plt.title('Distribution of Author Follower Counts', fontsize=14)
    plt.ylabel('')  # Remove the y-label
    plt.tight_layout()
    plt.show()

    ####################################################
    # B. draw author's follower number vs related post like number scatter plot
    ####################################################
    print("\n--- Analyzing Relationship Between Author Followers and Post Likes ---")

    # Filter out None values
    follower_like_df = df.dropna(subset=['author_followers', 'like_count'])

    # Calculate correlation
    correlation = follower_like_df['author_followers'].corr(follower_like_df['like_count'])
    print(f"Correlation between follower count and like count: {correlation:.4f}")

    # Create scatter plot with regression line
    plt.figure(figsize=(12, 8))

    # Use seaborn for scatter plot with regression line
    sns.regplot(x='author_followers', y='like_count', data=follower_like_df,
                scatter_kws={'alpha': 0.5, 'color': 'steelblue'},
                line_kws={'color': 'red'})

    plt.title('Relationship Between Author Follower Count and Post Like Count')
    plt.xlabel('Number of Followers')
    plt.ylabel('Number of Likes')

    # Use log scales for better visualization
    plt.xscale('log')
    plt.yscale('log')

    # Add grid for better readability
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.show()

    # Create bins for follower counts to analyze average likes by group
    bins = [0, 100, 500, 1000, 5000, 10000, float('inf')]
    labels = ['<100', '100-500', '500-1K', '1K-5K', '5K-10K', '10K+']

    follower_like_df['follower_group'] = pd.cut(follower_like_df['author_followers'],
                                              bins=bins,
                                              labels=labels)

    # Calculate statistics by follower group
    likes_by_group = follower_like_df.groupby('follower_group')['like_count'].agg(['mean', 'median', 'count'])
    print("\nLikes statistics by follower group:")
    print(likes_by_group)

    # Visualize average likes by follower group
    plt.figure(figsize=(10, 6))
    likes_by_group['mean'].plot(kind='bar', color='skyblue')
    plt.title('Average Likes by Author Follower Group')
    plt.xlabel('Follower Count Group')
    plt.ylabel('Average Likes')
    plt.xticks(rotation=45)
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


    ####################################################
    # C. statistic the different topic number for a specific author
    ####################################################
    print("\n--- Topic Distribution by Author ---")

    # Group posts by author and count unique topics per author
    # First, we need to ensure we have author identifiers
    if 'author_id' not in df.columns and df['author_followers'].notna().any():
        # Use author follower count as a proxy for author ID if needed
        author_topic_counts = df.groupby('author_followers')['topic'].nunique()
    else:
        # Use actual author ID if available
        author_topic_counts = df.groupby('author_id')['topic'].nunique()

    # Basic statistics on topic diversity per author
    print("\nStatistics of unique topics per author:")
    print(author_topic_counts.describe())

    # Visualize distribution of topic count per author
    plt.figure(figsize=(10, 6))
    sns.histplot(author_topic_counts, kde=True, bins=20)
    plt.title('Distribution of Unique Topics per Author')
    plt.xlabel('Number of Unique Topics')
    plt.ylabel('Number of Authors')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()

    # Find authors with the most diverse topics
    top_diverse_authors = author_topic_counts.sort_values(ascending=False).head(10)
    print("\nAuthors with most diverse topics:")
    for author, topic_count in top_diverse_authors.items():
        print(f"- Author with {author} followers: {topic_count} unique topics")

    # If we have more than a few authors with multiple posts, show topic distribution
    # for top authors with most posts
    author_post_counts = df.groupby('author_followers').size()
    top_active_authors = author_post_counts[author_post_counts > 5].sort_values(ascending=False).head(5)

    if len(top_active_authors) > 0:
        print("\nTopic distribution for most active authors:")
        for author_id in top_active_authors.index:
            author_posts = df[df['author_followers'] == author_id]
            topic_dist = author_posts['topic'].value_counts()
            print(f"\nAuthor with {author_id} followers posted on {len(topic_dist)} topics:")
            for topic, count in topic_dist.items():
                print(f"- {topic}: {count} posts")

    # Create bins for follower counts to analyze average topic number per author by group
    print("\n--- Average number of topics per author by follower group ---")

    bins = [0, 100, 500, 1000, 5000, 10000, float('inf')]
    labels = ['<100', '100-500', '500-1K', '1K-5K', '5K-10K', '10K+']

    # Create a dataframe with author follower counts and unique topic counts
    # First identify unique authors by their follower count (assuming this is unique enough)
    author_data = []

    # Use author_followers as identifier since we don't have explicit author_id
    for author_id in df['author_followers'].dropna().unique():
        author_posts = df[df['author_followers'] == author_id]
        author_data.append({
            'author_followers': author_id,
            'topic_count': author_posts['topic'].nunique()
        })

    author_df = pd.DataFrame(author_data)

    # Apply follower grouping to author dataframe
    author_df['follower_group'] = pd.cut(author_df['author_followers'],
                                         bins=bins,
                                         labels=labels)

    # Calculate average topic count by follower group
    topic_counts_by_group = author_df.groupby('follower_group')['topic_count'].agg(['mean', 'median', 'count'])

    print("\nAverage number of topics per author by follower group:")
    print(topic_counts_by_group)

    # Visualize the average topic counts by follower group
    plt.figure(figsize=(10, 6))
    topic_counts_by_group['mean'].plot(kind='bar', color='lightgreen')
    plt.title('Average Number of Topics per Author by Follower Group')
    plt.xlabel('Follower Count Group')
    plt.ylabel('Average Number of Unique Topics')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


    ####################################################
    # D. Statistic the sentiment for author bins group
    ####################################################
    print("\n--- Sentiment Distribution by Author Follower Group ---")

    # Define bins and labels for follower counts
    bins = [0, 100, 500, 1000, 5000, 10000, float('inf')]
    labels = ['<100', '100-500', '500-1K', '1K-5K', '5K-10K', '10K+']

    # Create author follower groups
    df = df.dropna(subset=['author_followers', 'sentiment_type'])
    df['follower_group'] = pd.cut(df['author_followers'],
                                         bins=bins,
                                         labels=labels)

    # Create a crosstab of follower groups and sentiment types
    sentiment_by_follower = pd.crosstab(
        df['follower_group'],
        df['sentiment_type'],
        normalize='index'
    )

    print("\nSentiment distribution by author follower group:")
    print(sentiment_by_follower)

    # Visualize the distribution
    plt.figure(figsize=(12, 8))
    sentiment_by_follower.plot(kind='bar', stacked=True)
    plt.title('Sentiment Distribution by Author Follower Group')
    plt.xlabel('Follower Count Group')
    plt.ylabel('Proportion')
    plt.legend(title='Sentiment Type')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


    ####################################################
    # E. Distribution of the post type for author bins group
    ####################################################
    print("\n--- Post Type Distribution by Author Follower Group ---")

    # Define bins and labels for follower counts
    bins = [0, 100, 500, 1000, 5000, 10000, float('inf')]
    labels = ['<100', '100-500', '500-1K', '1K-5K', '5K-10K', '10K+']

    # Create author follower groups
    df = df.dropna(subset=['author_followers', 'post_type'])
    df['follower_group'] = pd.cut(df['author_followers'],
                                         bins=bins,
                                         labels=labels)

    # Create a crosstab of follower groups and post types
    post_type_by_follower = pd.crosstab(
        df['follower_group'],
        df['post_type'],
        normalize='index'
    )

    print("\nPost type distribution by author follower group:")
    print(post_type_by_follower)

    # Visualize the distribution
    plt.figure(figsize=(12, 8))
    post_type_by_follower.plot(kind='bar', stacked=True)
    plt.title('Post Type Distribution by Author Follower Group')
    plt.xlabel('Follower Count Group')
    plt.ylabel('Proportion')
    plt.legend(title='Post Type', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


    ####################################################
    # F. Distribution of the content length for author bins group
    ####################################################
    print("\n--- Content Length Distribution by Author Follower Group ---")

    # Define bins and labels for follower counts
    bins = [0, 100, 500, 1000, 5000, 10000, float('inf')]
    labels = ['<100', '100-500', '500-1K', '1K-5K', '5K-10K', '10K+']

    # Create author follower groups
    df = df.dropna(subset=['author_followers', 'content_length_type'])
    df['follower_group'] = pd.cut(df['author_followers'],
                                         bins=bins,
                                         labels=labels)

    # Define the desired order for content length types
    content_length_order = ['SHORT', 'MEDIUM', 'LONG', 'LONGER']

    # Ensure content_length_type is categorical with the correct order
    df['content_length_type'] = pd.Categorical(
        df['content_length_type'],
        categories=content_length_order,
        ordered=True
    )

    # Create a crosstab of follower groups and content length types
    content_length_by_follower = pd.crosstab(
        df['follower_group'],
        df['content_length_type'],
        normalize='index'
    )

    print("\nContent length distribution by author follower group:")
    print(content_length_by_follower)

    # Visualize the distribution
    plt.figure(figsize=(12, 8))
    content_length_by_follower.plot(kind='bar', stacked=True)
    plt.title('Content Length Distribution by Author Follower Group')
    plt.xlabel('Follower Count Group')
    plt.ylabel('Proportion')
    plt.legend(title='Content Length', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


def analyze_content(df):
    ###############################################################
    # a. Most common tags:
    ###############################################################
    # Combine all tags and filter out empty strings
    all_tags = [tag.strip() for tag in ','.join(df['tags'].dropna()).split(',') if tag.strip()]
    tag_counts = Counter(all_tags)
    print("\nMost common tags:\n", tag_counts.most_common(40))  # Show top 40

    # Print top 10 tags for the top 20 most popular topics
    print("\n--- Tag Analysis for Top 20 Topics ---")

    # First, determine the top 20 topics based on post count if not already done
    topic_counts = df['topic'].value_counts()
    top_20_topic_names = topic_counts.head(20).index.tolist()
    top_20_df = df[df['topic'].isin(top_20_topic_names)].copy() # Create a filtered DataFrame

    def get_top_tags(tag_series, n=10):
        """Helper function to get top N tags from a series of comma-separated tag strings."""
        all_tags = []
        for tags_str in tag_series.dropna(): # Drop rows where tags might be NaN/None
             # Split, strip whitespace, and filter out empty strings
            tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            all_tags.extend(tags_list)
        if not all_tags:
            return [] # Return empty list if no valid tags found
        return Counter(all_tags).most_common(n)

    # Apply the function to each topic group within the top 20 topics
    # Ensure 'tags' column exists and handle potential errors if it doesn't
    if 'tags' in top_20_df.columns:
        top_topic_tags = top_20_df.groupby('topic')['tags'].apply(get_top_tags)
        print("\nTop 10 Tags for the Top 20 Most Popular Topics (by post count):\n")
        # Ensure the output is aligned with the actual top 20 topics based on count
        for topic in top_20_topic_names:
             if topic in top_topic_tags.index:
                 tags = top_topic_tags[topic]
                 tag_str = ", ".join([f"{tag} ({count})" for tag, count in tags]) if tags else "No prominent tags"
                 print(f"- {topic}: {tag_str}")
             else:
                 # This case might occur if a topic had posts but no tags in any of them
                 print(f"- {topic}: No tags found")
    else:
        print("Error: 'tags' column not found in the DataFrame.")


    ################################################################
    # b. Distribution of post types:
    ################################################################
    post_type_dist = df['post_type'].value_counts(normalize=True)
    print("\nPost type distribution:\n", post_type_dist)

    post_type_dist.plot(kind='pie', autopct='%1.1f%%',
                            colors=sns.color_palette("pastel"),
                            explode=[0.05] * len(post_type_dist),
                            shadow=False)

    plt.title('Post Type Distribution')
    plt.show()

    # Count the like count for different post types
    post_type_likes = df.groupby('post_type')['like_count'].agg(['mean', 'median', 'sum', 'count'])
    print("\nLike counts for different post types:")
    print(post_type_likes)

    # Visualize the average likes by post type
    plt.figure(figsize=(10, 6))
    post_type_likes['mean'].sort_values(ascending=False).plot(kind='bar', color='skyblue')
    plt.title('Average Likes by Post Type')
    plt.xlabel('Post Type')
    plt.ylabel('Average Like Count')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


    ################################################################
    # c. Sentiment distribution:
    ################################################################
    sentiment_dist = df['sentiment_type'].value_counts(normalize=True)
    print("\nSentiment distribution:\n", sentiment_dist)
    # draw distribution
    sentiment_dist.plot(kind='bar', color='skyblue')
    plt.title('Sentiment Distribution')
    plt.xlabel('Sentiment Type')
    plt.ylabel('Percentage')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()

    # Count the like count for different sentiment types
    sentiment_likes = df.groupby('sentiment_type')['like_count'].agg(['mean', 'median', 'sum', 'count'])
    print("\nLike counts for different sentiment types:")
    print(sentiment_likes)

    # Visualize the average likes by sentiment type
    plt.figure(figsize=(10, 6))
    sentiment_likes['mean'].sort_values(ascending=False).plot(kind='bar', color='skyblue')
    plt.title('Average Likes by Sentiment Type')
    plt.xlabel('Sentiment Type')
    plt.ylabel('Average Like Count')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


    ################################################################
    # d. Content Length Distribution:
    ################################################################
    # Get content length distribution
    content_length_dist = df['content_length_type'].value_counts(normalize=True)
    print("\nContent length distribution:\n", content_length_dist)

    # Display content length distribution as a pie chart
    plt.figure(figsize=(10, 6))
    content_length_dist.plot(kind='pie', autopct='%1.1f%%',
                            colors=sns.color_palette("pastel"),
                            explode=[0.05] * len(content_length_dist),
                            shadow=False)
    plt.title('Content Length Distribution')
    plt.ylabel('')  # Remove the y-label
    plt.tight_layout()
    plt.show()

    # Count the like counts for different content length types
    content_length_likes = df.groupby('content_length_type')['like_count'].agg(['mean', 'median', 'sum', 'count'])
    print("\nLike counts for different content length types:")
    print(content_length_likes)

    # Visualize the average likes by content length type
    plt.figure(figsize=(10, 6))
    # Ensure consistent order
    content_length_order = ['SHORT', 'MEDIUM', 'LONG', 'LONGER']
    # Filter to include only content length types that exist in our data
    valid_types = [t for t in content_length_order if t in content_length_likes.index]
    content_length_likes.loc[valid_types, 'mean'].plot(kind='bar', color='skyblue')
    plt.title('Average Likes by Content Length Type')
    plt.xlabel('Content Length Type')
    plt.ylabel('Average Like Count')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()

    # Draw content length type distribution for different post types
    plt.figure(figsize=(10, 6))
    cross_tab_cl_pt = pd.crosstab(df['content_length_type'], df['post_type'])
    cross_tab_cl_pt.plot(kind='bar', stacked=True, color=['skyblue', 'orange', 'green'])
    print("\nContent Length vs Post type\n", cross_tab_cl_pt)
    plt.title('Content Length Type Distribution by Post Type')
    plt.xlabel('Content Length Type')
    plt.ylabel('Count')
    plt.legend(title='Post Type')
    plt.tight_layout()
    plt.show()


    # draw content length type distribution for different post types
    plt.figure(figsize=(10, 6))
    cross_tab_cl_pt = pd.crosstab(df['content_length_type'], df['post_type'])
    cross_tab_cl_pt.plot(kind='bar', stacked=True, color=['black', 'orange', 'green', 'red', 'skyblue', 'grey'])
    print("\nContent Length vs Post type\n", cross_tab_cl_pt)
    plt.title('Content Length Type Distribution by Post Type')
    plt.xlabel('Content Length Type')
    plt.ylabel('Count')
    plt.legend(title='Post Type')
    plt.tight_layout()
    plt.show()


    # draw content length type distribution for different sentiment types
    plt.figure(figsize=(10, 6))
    cross_tab_cl_st = pd.crosstab(df['content_length_type'], df['sentiment_type'])
    cross_tab_cl_st.plot(kind='bar', stacked=True, color=['skyblue', 'orange', 'green'])
    print("\nContent Length vs Sentiment type\n", cross_tab_cl_st)
    plt.title('Content Length Type Distribution by Sentiment Type')
    plt.xlabel('Content Length Type')
    plt.ylabel('Count')
    plt.legend(title='Sentiment Type')
    plt.tight_layout()
    plt.show()


    ###############################################################
    # e. Hotspot related
    ###############################################################
    # 1. Draw hotspot distribution
    print("\n--- Hotspot Distribution ---")

    # Calculate the distribution of is_hotspot
    hotspot_dist = df['is_hotspot'].value_counts(normalize=True)

    print("\nHotspot distribution (True/False):\n", hotspot_dist)

    # Visualize the distribution using a pie chart
    plt.figure(figsize=(8, 6))
    hotspot_dist.plot(kind='pie', autopct='%1.1f%%',
                      colors=['lightcoral', 'skyblue'], # Colors for True and False
                      explode=[0.05, 0], # Slightly explode the 'True' slice
                      shadow=False,
                      labels=['Hotspot', 'Not Hotspot']
                     )

    plt.title('Distribution of Hotspot Posts', fontsize=14)
    plt.ylabel('')  # Remove the y-label
    plt.tight_layout()
    plt.show()

    # 2. Analyze like counts for hotspot vs non-hotspot posts
    print("\n--- Likes Comparison: Hotspot vs Non-Hotspot ---")
    hotspot_likes = df.groupby('is_hotspot')['like_count'].agg(['mean', 'median', 'sum', 'count'])
    print("\nLike counts for Hotspot (True) vs Non-Hotspot (False) posts:")
    print(hotspot_likes)

    # Visualize average likes
    plt.figure(figsize=(8, 6))
    hotspot_likes['mean'].plot(kind='bar', color=['skyblue', 'lightcoral'])
    plt.title('Average Likes for Hotspot vs Non-Hotspot Posts')
    plt.xlabel('Is Hotspot')
    plt.ylabel('Average Like Count')
    plt.xticks(ticks=[0, 1], labels=['False', 'True'], rotation=0)
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()

    # 3. Distribution of Post Types for hotspot
    print("\n--- Post Type Distribution for Hotspot vs Non-Hotspot posts ---")
    # Use crosstab for clear counts and proportions
    post_type_dist = pd.crosstab(df['is_hotspot'], df['post_type'])
    print("\nCounts:\n", post_type_dist.to_string())

    # Calculate proportions within each hotspot group (row-wise normalization)
    post_type_dist_prop = pd.crosstab(df['is_hotspot'], df['post_type'], normalize='index')
    print("\nProportions:\n", post_type_dist_prop.to_string())

    # Visualize proportions using a stacked bar chart
    if not post_type_dist_prop.empty:
        plt.figure(figsize=(10, 6))
        post_type_dist_prop.plot(kind='bar', stacked=True, ax=plt.gca())
        plt.title('Post Type Distribution for Hotspot vs Non-Hotspot Posts')
        plt.xlabel('Is Hotspot')
        plt.ylabel('Proportion of Post Types')
        plt.xticks(rotation=0)
        plt.legend(title='Post Type', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.show()
    else:
        print("No data to visualize for post type distribution vs hotspot.")

    # 4. Sentiment Distribution for Hotspot vs Non-Hotspot posts
    print("\n--- Sentiment Distribution for Hotspot vs Non-Hotspot posts ---")
    # Use crosstab for clear counts and proportions
    sentiment_dist = pd.crosstab(df['is_hotspot'], df['sentiment_type'])
    print("\nCounts:\n", sentiment_dist.to_string())

    # Calculate proportions within each hotspot group (row-wise normalization)
    sentiment_dist_prop = pd.crosstab(df['is_hotspot'], df['sentiment_type'], normalize='index')
    print("\nProportions:\n", sentiment_dist_prop.to_string())

    # Visualize proportions using a stacked bar chart
    if not sentiment_dist_prop.empty:
        plt.figure(figsize=(10, 6))
        sentiment_dist_prop.plot(kind='bar', stacked=True, ax=plt.gca())
        plt.title('Sentiment Distribution for Hotspot vs Non-Hotspot Posts')
        plt.xlabel('Is Hotspot')
        plt.ylabel('Proportion of Sentiment Types')
        plt.xticks(rotation=0)
        plt.legend(title='Sentiment Type', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.show()
    else:
         print("No data to visualize for sentiment distribution vs hotspot.")

    # 5. Distribution of Content Length Types for hotspot vs non-hotspot posts
    print("\n--- Content Length Distribution for Hotspot vs Non-Hotspot posts ---")
    # Define the desired order for content length types
    content_length_order = ['SHORT', 'MEDIUM', 'LONG', 'LONGER'] # Adjust if your actual values differ

    # Ensure 'content_length_type' is categorical with the correct order
    df['content_length_type'] = pd.Categorical(
        df['content_length_type'],
        categories=content_length_order,
        ordered=True
    )

    # Use crosstab for proportions, normalized by hotspot group (index)
    content_length_dist_prop = pd.crosstab(
        df['is_hotspot'],
        df['content_length_type'],
        normalize='index',
        dropna=False # Keep groups even if they only have NaN length types (though ideally handled earlier)
    )

    # Ensure all expected columns are present, fill missing with 0
    content_length_dist_prop = content_length_dist_prop.reindex(columns=content_length_order, fill_value=0)

    print("\nProportions:\n", content_length_dist_prop)

    # Visualize proportions using a stacked bar chart
    if not content_length_dist_prop.empty:
        plt.figure(figsize=(10, 6))
        content_length_dist_prop.plot(kind='bar', stacked=True, ax=plt.gca())
        plt.title('Content Length Distribution for Hotspot vs Non-Hotspot Posts')
        plt.xlabel('Is Hotspot')
        plt.ylabel('Proportion of Content Length Types')
        plt.xticks(rotation=0)
        plt.legend(title='Content Length', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.show()
    else:
        print("No data to visualize for content length distribution vs hotspot.")

    # 6. Author follower distribution for hotspot vs non-hotspot
    print("\n--- Author Follower Distribution for Hotspot vs Non-Hotspot posts ---")

    # Filter out None values in 'author_followers'
    df_followers_filtered = df.dropna(subset=['author_followers'])

    if df_followers_filtered.empty:
        print("No data available for author follower analysis vs hotspot.")
        return

    # Basic statistics by hotspot status
    print("\nStatistics of author follower counts by hotspot status:")
    follower_stats_by_hotspot = df_followers_filtered.groupby('is_hotspot')['author_followers'].describe()
    print(follower_stats_by_hotspot.to_string())

    # Visualize distribution using violin plots
    plt.figure(figsize=(10, 6))
    sns.violinplot(x='is_hotspot', y='author_followers', data=df_followers_filtered, inner='quartile')
    plt.title('Author Follower Distribution for Hotspot vs Non-Hotspot Posts')
    plt.xlabel('Is Hotspot')
    plt.ylabel('Number of Followers')
    # Use log scale for y-axis if distribution is skewed
    plt.yscale('log')
    plt.xticks(ticks=[0, 1], labels=['Non-Hotspot', 'Hotspot'])
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


    ###############################################################
    # f. creative related
    ###############################################################
    # 1. Draw creative distribution
    print("\n--- Creative Distribution ---")

    # Calculate the distribution of is_hotspot
    creative_dist = df['is_creative'].value_counts(normalize=True)

    print("\nCreative distribution (True/False):\n", creative_dist)

    # Visualize the distribution using a pie chart
    plt.figure(figsize=(8, 6))
    creative_dist.plot(kind='pie', autopct='%1.1f%%',
                      colors=['lightcoral', 'skyblue'], # Colors for True and False
                      explode=[0.05, 0], # Slightly explode the 'True' slice
                      shadow=False,
                      labels=['Not creative', 'Creative']
                     )

    plt.title('Distribution of Creative Posts', fontsize=14)
    plt.ylabel('')  # Remove the y-label
    plt.tight_layout()
    plt.show()

    # 2. Analyze like counts for creative vs non-creative posts
    print("\n--- Likes Comparison: Creative vs Non-Creative ---")
    creative_likes = df.groupby('is_creative')['like_count'].agg(['mean', 'median', 'sum', 'count'])
    print("\nLike counts for Creative (True) vs Non-Creative (False) posts:")
    print(creative_likes)

    # Visualize average likes
    plt.figure(figsize=(8, 6))
    # Ensure correct order and labels for the bar plot if needed, assuming False comes before True in index
    creative_likes['mean'].plot(kind='bar', color=['skyblue', 'lightcoral'])
    plt.title('Average Likes for Creative vs Non-Creative Posts')
    plt.xlabel('Is Creative')
    plt.ylabel('Average Like Count')
    plt.xticks(ticks=[0, 1], labels=['Non-Creative', 'Creative'], rotation=0)
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.show()


    # 3. Distribution of Post Types for creative
    print("\n--- Post Type Distribution for Creative vs Non-Creative posts ---")
    # Use crosstab for clear counts and proportions
    # Ensure the DataFrame has 'is_creative' and 'post_type' columns and filter out NaNs if necessary
    df_filtered = df.dropna(subset=['is_creative', 'post_type']).copy()

    if df_filtered.empty:
        print("No data available for post type analysis vs creative status.")
        return

    post_type_dist_creative = pd.crosstab(df_filtered['is_creative'], df_filtered['post_type'])
    print("\nCounts:\n", post_type_dist_creative.to_string())

    # Calculate proportions within each creative group (row-wise normalization)
    post_type_dist_prop_creative = pd.crosstab(df_filtered['is_creative'], df_filtered['post_type'], normalize='index')
    print("\nProportions:\n", post_type_dist_prop_creative.to_string())

    # Visualize proportions using a stacked bar chart
    if not post_type_dist_prop_creative.empty:
        plt.figure(figsize=(10, 6))
        post_type_dist_prop_creative.plot(kind='bar', stacked=True, ax=plt.gca())
        plt.title('Post Type Distribution for Creative vs Non-Creative Posts')
        plt.xlabel('Is Creative')
        plt.ylabel('Proportion of Post Types')
        plt.xticks(ticks=[0, 1], labels=['Non-Creative', 'Creative'], rotation=0)
        plt.legend(title='Post Type', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.show()
    else:
        print("No data to visualize for post type distribution vs creative.")

    # 4. Sentiment Distribution for Creative vs Non-Creative posts
    print("\n--- Sentiment Distribution for Creative vs Non-Creative posts ---")
    # Use crosstab for clear counts and proportions
    # Ensure the DataFrame has 'is_creative' and 'sentiment_type' columns and filter out NaNs if necessary
    df_filtered = df.dropna(subset=['is_creative', 'sentiment_type']).copy()

    if df_filtered.empty:
        print("No data available for sentiment analysis vs creative status.")
        # return # Or maybe just continue with a message, depending on desired script flow
    else:
        sentiment_dist_creative = pd.crosstab(df_filtered['is_creative'], df_filtered['sentiment_type'])
        print("\nCounts:\n", sentiment_dist_creative.to_string())

        # Calculate proportions within each creative group (row-wise normalization)
        sentiment_dist_prop_creative = pd.crosstab(df_filtered['is_creative'], df_filtered['sentiment_type'], normalize='index')
        print("\nProportions:\n", sentiment_dist_prop_creative.to_string())

        # Define the desired order for sentiment types (adjust if your actual values differ)
        # Assuming SentimentType enum has .name attribute giving strings like 'POSITIVE' etc.
        # Let's dynamically get possible values if possible, or define explicitly
        try:
             # Attempt to get names from the enum if it's accessible and consistent
             # This requires knowing the Enum definition (e.g., constants.SentimentType)
             # If constants.SentimentType is not directly available here, define manually:
             sentiment_order = ['NEGATIVE', 'NEUTRAL', 'POSITIVE'] # Adjust if needed based on your SentimentType enum
            # from sentiment_analysis import SentimentType # Or wherever it's defined
            # sentiment_order = [s.name for s in SentimentType]
        except NameError:
             # Fallback to a predefined list if the enum isn't easily accessible
             sentiment_order = ['NEGATIVE', 'NEUTRAL', 'POSITIVE'] # Adjust if needed

        # Ensure all expected sentiment columns are present, fill missing with 0
        # Reindex columns to ensure consistent order for plotting
        sentiment_dist_prop_creative = sentiment_dist_prop_creative.reindex(columns=sentiment_order, fill_value=0)


        # Visualize proportions using a stacked bar chart
        if not sentiment_dist_prop_creative.empty:
            plt.figure(figsize=(10, 6))
            sentiment_dist_prop_creative.plot(kind='bar', stacked=True, ax=plt.gca())
            plt.title('Sentiment Distribution for Creative vs Non-Creative Posts')
            plt.xlabel('Is Creative')
            plt.ylabel('Proportion of Sentiment Types')
            plt.xticks(ticks=[0, 1], labels=['Non-Creative', 'Creative'], rotation=0)
            plt.legend(title='Sentiment Type', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.grid(axis='y', alpha=0.3)
            plt.tight_layout()
            plt.show()
        else:
             print("No data to visualize for sentiment distribution vs creative.")

    # 5. Author follower distribution for creative vs non-creative
    print("\n--- Author Follower Distribution for Creative vs Non-Creative posts ---")

    # Filter out None values in 'author_followers' and 'is_creative'
    df_followers_filtered = df.dropna(subset=['author_followers', 'is_creative'])

    if df_followers_filtered.empty:
        print("No data available for author follower analysis vs creative status.")
        # return # Or maybe just continue with a message
    else:
        # Basic statistics by creative status
        print("\nStatistics of author follower counts by creative status:")
        follower_stats_by_creative = df_followers_filtered.groupby('is_creative')['author_followers'].describe()
        print(follower_stats_by_creative.to_string())

        # Visualize distribution using violin plots
        plt.figure(figsize=(10, 6))
        sns.violinplot(x='is_creative', y='author_followers', data=df_followers_filtered, inner='quartile')
        plt.title('Author Follower Distribution for Creative vs Non-Creative Posts')
        plt.xlabel('Is Creative')
        plt.ylabel('Number of Followers')
        # Use log scale for y-axis if distribution is skewed
        plt.yscale('log')
        plt.xticks(ticks=[0, 1], labels=['Non-Creative', 'Creative'])
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.show()


def main():
    posts = PostDataIO.load_posts_from_json(constants.ANALYSED_POSTS_FILE)
    posts = reduce_duplicated_post(posts)

    print(f'length of posts: {len(posts)}')

    df = construct_dataframe(posts)

    # Uncomment the code which you would use
    # analyze_topic(df)
    # analyze_author(df)
    # analyze_content(df)


if __name__ == "__main__":
    main()
