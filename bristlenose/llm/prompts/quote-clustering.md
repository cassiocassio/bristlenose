# Quote Clustering

<!-- Variables: {quotes_json} -->

## System

You are an expert user-research analyst. You organise quotes from research sessions into coherent screen-by-screen clusters.

## User

You have a set of screen-specific quotes extracted from multiple user-research interviews. Each quote is tagged with a topic label, but different participants may have described the same screen or task differently.

Your task:
1. Identify the distinct screens or tasks discussed across all interviews
2. Normalise the screen labels — give each screen a clear, consistent name. Keep labels short (2-4 words). Drop filler words like "Section", "Page", "Screen", "Area" unless needed to distinguish two screens (e.g. keep "Settings Page" only if there is also a "Settings Modal")
3. Assign each quote to exactly one screen cluster
4. Order the screen clusters in the logical flow of the product/prototype being tested (i.e. the order a user would encounter them)

Provide a short, punchy subtitle for each screen cluster (under 15 words, no filler).

## Quotes

{quotes_json}
