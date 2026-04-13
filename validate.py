import pandas as pd

df = pd.read_csv("tmdb_5000_movies.csv")

# Filter out movies with missing/zero revenue or vote data
df = df[(df['revenue'] > 0) & (df['vote_count'] > 100) & (df['vote_average'] > 0)]

# Pick 5 blockbusters (revenue > 500M)
blockbusters = df.nlargest(5, 'revenue')[['title', 'revenue', 'vote_average', 'budget', 'popularity']]

# Pick 5 mid-range (revenue 10M - 100M)
mid = df[df['revenue'].between(10_000_000, 100_000_000)].nlargest(5, 'vote_average')[['title', 'revenue', 'vote_average', 'budget', 'popularity']]

# Pick 5 low budget / flops (revenue < 5M)
low = df[df['revenue'] < 5_000_000].nlargest(5, 'vote_count')[['title', 'revenue', 'vote_average', 'budget', 'popularity']]

# Pick 5 classics (before 2000)
df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
classics = df[df['release_date'] < '2000-01-01'].nlargest(5, 'vote_average')[['title', 'revenue', 'vote_average', 'budget', 'popularity']]

# Combine all 20
test_set = pd.concat([
    blockbusters.assign(category='Blockbuster'),
    mid.assign(category='Mid-range'),
    low.assign(category='Low budget'),
    classics.assign(category='Classic')
]).reset_index(drop=True)

# Format revenue and budget for readability
test_set['revenue_fmt'] = test_set['revenue'].apply(lambda x: f"${x:,.0f}")
test_set['budget_fmt'] = test_set['budget'].apply(lambda x: f"${x:,.0f}")

print(test_set[['category', 'title', 'revenue_fmt', 'budget_fmt', 'vote_average']].to_string())

# Save to CSV for reference
test_set.to_csv("test_movies.csv", index=False)
print("\nSaved to test_movies.csv")