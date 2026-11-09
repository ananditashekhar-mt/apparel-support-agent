# Local phone preview

The preview embeds the actual Streamlit web application at 360, 390, or 430 CSS pixels wide. It is not a separate native mobile app. Each embedded app session has its own chat state.

From the project folder, run these in separate terminals:

```sh
.venv/bin/streamlit run app.py --server.port 8503 --server.address 127.0.0.1
.venv/bin/python -m http.server 8505 --bind 127.0.0.1 --directory preview/mobile
```

Open http://127.0.0.1:8505/ and use the Screen width selector. Scroll inside the phone to test the order and chat flows. Open http://127.0.0.1:8503/ for the desktop layout.

These addresses work on this computer only. A physical phone will use the hosted URL after deployment. You can also use your browser's responsive device mode to check any local app URL.
