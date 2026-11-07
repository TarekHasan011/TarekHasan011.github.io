# Md. Tarek Hasan — personal website

## Run it

```
python server.py
```

Then open http://localhost:8080.

## Publish on GitHub Pages

The workflow in `.github/workflows/pages.yml` publishes the `site/` folder. Once a day (06:30 Dhaka time) it also runs `refresh_data.py` to update citations, publications, journal metrics and abstracts from Google Scholar, then redeploys.

1. Create a public repository on GitHub. Name it `<username>.github.io` for the address `https://<username>.github.io`; any other name gives `https://<username>.github.io/<repo-name>`.
2. Push this folder to the `main` branch:
   ```
   git init -b main
   git add .
   git commit -m "Personal website"
   git remote add origin https://github.com/<username>/<repo-name>.git
   git push -u origin main
   ```
3. In the repository, open **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Open the **Actions** tab, choose **Update data and deploy**, and click **Run workflow** once. The site goes live when it finishes. After that it refreshes itself every day, and every push redeploys it.
5. Optional: for live Scopus quartiles, add a repository secret named `ELSEVIER_API_KEY` (**Settings → Secrets and variables → Actions**).

If Google Scholar blocks the daily request, the site keeps showing the last saved data.

## Folders

| Folder / file | What it holds |
|---|---|
| `server.py` | Local server. Serves the site and fetches live Google Scholar, journal metrics and paper abstracts. |
| `refresh_data.py` | Updates the saved data in `site/data/` (run daily by the GitHub Action; can also be run by hand). |
| `.github/workflows/pages.yml` | GitHub Action: daily data refresh and deployment to GitHub Pages. |
| `config.json` | Local settings, such as an optional Elsevier API key for live Scopus quartiles. Not committed to Git (see `.gitignore`); copy `config.example.json` to `config.json` to create it. The key can also be set as the `ELSEVIER_API_KEY` environment variable. |
| `config.example.json` | Safe template of `config.json`, without any key. |
| `site/` | The website itself. This is the folder to upload when hosting. |
| `site/index.html` | All page content. |
| `site/assets/css/`, `site/assets/js/` | Styles and scripts. |
| `site/assets/img/` | Web-ready images (resized JPG + WebP), with organisation logos in `logos/`. |
| `site/assets/docs/` | The CV PDF linked from the "View CV" button. |
| `site/data/` | `curated.json` (manual paper details, editable) and data saved automatically by the server. |
| `source-files/` | Original, full-size material. Not used by the site directly, and not committed to Git (large, and the CV sources hold private contact details). |
| `source-files/cv/` | CV PDF and its LaTeX source. |
| `source-files/photos/` | Original photos (portrait, graduation, medals, Blockchain Olympiad, convocations). |
| `source-files/press/` | Ajker Patrika newspaper clipping and its e-paper link. |
| `source-files/logos/` | Original logo files. |
| `source-files/links.txt` | Useful links (videos, profiles). |

To change a photo on the site, keep the original in `source-files/photos/` and put a resized copy in `site/assets/img/`.
