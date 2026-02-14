name: Update fixtures.json

on:
  schedule:
    - cron: "0 */6 * * *"   # every 6 hours
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: pip install requests beautifulsoup4

      - name: Scrape and generate JSON
        run: python scrape.py

      - name: Commit and push
        run: |
          git config user.name "fixtures-bot"
          git config user.email "fixtures-bot@users.noreply.github.com"
          git add fixtures.json
          git commit -m "Update fixtures.json" || exit 0
          git push
