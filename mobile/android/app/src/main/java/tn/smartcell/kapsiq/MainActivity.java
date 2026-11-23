package tn.smartcell.kapsiq;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.provider.MediaStore;
import android.text.InputType;
import android.util.Base64;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.inputmethod.EditorInfo;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Scanner;

/**
 * Application Android Kapsi-Q (SmartCell Technologies).
 * Affiche Kapsi-Q, installé sur le poste du cabinet, en plein écran.
 * Au premier lancement, l'utilisateur saisit l'adresse affichée dans Réglages → Connecter un téléphone.
 */
public class MainActivity extends Activity {
    private static final String PREFS = "kapsiq";
    private static final String KEY_SERVER = "server";
    private static final int BG = 0xFF1A060D;
    private static final int PINK = 0xFFE8327F;
    private static final int VIOLET = 0xFF7B2FF7;

    private FrameLayout root;
    private WebView web;
    private SharedPreferences prefs;
    private String server;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        root = new FrameLayout(this);
        root.setBackgroundColor(BG);
        setContentView(root);
        // Android 15 : affichage bord à bord ; on réserve la place des barres système et du clavier
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                Insets b = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                v.setPadding(b.left, b.top, b.right, b.bottom);
            } else {
                v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        server = prefs.getString(KEY_SERVER, null);
        if (server == null) showSetup(null);
        else openServer(server);
    }

    private int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    private Button button(String label, int color, boolean filled) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextSize(16);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        GradientDrawable bg = new GradientDrawable();
        bg.setCornerRadius(dp(28));
        if (filled) {
            bg.setColors(new int[]{PINK, VIOLET});
            bg.setOrientation(GradientDrawable.Orientation.LEFT_RIGHT);
            b.setTextColor(Color.WHITE);
        } else {
            bg.setColor(Color.TRANSPARENT);
            bg.setStroke(dp(2), color);
            b.setTextColor(color);
        }
        b.setBackground(bg);
        b.setMinHeight(dp(52));
        return b;
    }

    private TextView text(String s, float size, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(size);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setGravity(Gravity.CENTER_HORIZONTAL);
        t.setLineSpacing(0, 1.15f);
        return t;
    }

    private LinearLayout.LayoutParams lp(int top) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        p.topMargin = dp(top);
        return p;
    }

    /** Écran de configuration : adresse du poste Kapsi-Q du cabinet. */
    private void showSetup(String error) {
        root.removeAllViews();
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        box.setPadding(dp(28), dp(48), dp(28), dp(28));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.mipmap.ic_launcher);
        box.addView(logo, new LinearLayout.LayoutParams(dp(88), dp(88)));
        box.addView(text("Kapsi-Q", 30, Color.WHITE, true), lp(16));
        box.addView(text("Plateforme ISO du cabinet", 15, 0xFFE6C6D8, false), lp(4));
        box.addView(text("Sur le PC du cabinet, ouvrez Kapsi-Q → Réglages → « Connecter un téléphone » et saisissez l'adresse affichée. Le téléphone doit être sur le même Wi-Fi.", 15, 0xFFF3DDE8, false), lp(28));

        final EditText input = new EditText(this);
        input.setHint("ex. 192.168.1.25:8000");
        input.setHintTextColor(0xFF9A8496);
        input.setTextColor(0xFF1F1024);
        input.setTextSize(18);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setImeOptions(EditorInfo.IME_ACTION_GO);
        input.setPadding(dp(16), dp(14), dp(16), dp(14));
        GradientDrawable ibg = new GradientDrawable();
        ibg.setColor(Color.WHITE);
        ibg.setCornerRadius(dp(12));
        input.setBackground(ibg);
        String last = prefs.getString("last", "");
        input.setText(last);
        input.setContentDescription("Adresse de Kapsi-Q");
        box.addView(input, lp(24));

        final TextView status = text(error == null ? "" : error, 15, 0xFFFF8FAF, false);
        box.addView(status, lp(12));
        final ProgressBar progress = new ProgressBar(this);
        progress.setVisibility(View.GONE);
        box.addView(progress, lp(8));

        final Button go = button("Se connecter", PINK, true);
        box.addView(go, lp(16));

        Runnable connect = () -> {
            final String url = normalize(input.getText().toString());
            if (url == null) {
                status.setText("Saisissez l'adresse affichée sur le PC, par exemple 192.168.1.25:8000.");
                return;
            }
            prefs.edit().putString("last", input.getText().toString().trim()).apply();
            status.setText("");
            progress.setVisibility(View.VISIBLE);
            go.setEnabled(false);
            new Thread(() -> {
                final boolean ok = check(url);
                runOnUiThread(() -> {
                    progress.setVisibility(View.GONE);
                    go.setEnabled(true);
                    if (ok) {
                        prefs.edit().putString(KEY_SERVER, url).apply();
                        openServer(url);
                    } else {
                        status.setText("Kapsi-Q est introuvable à cette adresse. Vérifiez que le PC du cabinet est allumé, que Kapsi-Q est lancé et que le téléphone est sur le même Wi-Fi.");
                    }
                });
            }).start();
        };
        go.setOnClickListener(v -> connect.run());
        input.setOnEditorActionListener((v, actionId, ev) -> { connect.run(); return true; });

        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        scroll.addView(box);
        root.addView(scroll);
        web = null;
    }

    /** Accepte « 192.168.1.25 », « 192.168.1.25:8000 » ou une adresse complète. */
    static String normalize(String raw) {
        String s = raw == null ? "" : raw.trim();
        if (s.isEmpty()) return null;
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://" + s;
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        try {
            URL u = new URL(s);
            if (u.getHost() == null || u.getHost().isEmpty()) return null;
            if (u.getPort() == -1 && u.getProtocol().equals("http")) s = s + ":8000";
            return s;
        } catch (Exception e) {
            return null;
        }
    }

    /** Vérifie que l'adresse répond comme un serveur Kapsi-Q. */
    private static boolean check(String url) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url + "/api/health").openConnection();
            c.setConnectTimeout(5000);
            c.setReadTimeout(5000);
            if (c.getResponseCode() != 200) return false;
            try (InputStream in = c.getInputStream(); Scanner sc = new Scanner(in, "UTF-8").useDelimiter("\\A")) {
                String body = sc.hasNext() ? sc.next() : "";
                return body.contains("\"status\":\"ok\"");
            }
        } catch (Exception e) {
            return false;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private void openServer(String url) {
        server = url;
        root.removeAllViews();
        web = new WebView(this);
        web.setBackgroundColor(BG);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setTextZoom(100);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setAllowFileAccess(false);
        s.setUserAgentString(s.getUserAgentString() + " KapsiQ-Android/1.0.0");
        web.addJavascriptInterface(new Bridge(), "KapsiNative");
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                Uri base = Uri.parse(server);
                if (u.getHost() != null && u.getHost().equals(base.getHost()) && u.getPort() == base.getPort()) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (ActivityNotFoundException ignored) { }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) showOffline();
            }
        });
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        web.loadUrl(url);
    }

    /** Écran affiché si le poste du cabinet ne répond pas. */
    private void showOffline() {
        root.removeAllViews();
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setPadding(dp(28), dp(28), dp(28), dp(28));
        box.addView(text("Connexion impossible", 24, Color.WHITE, true), lp(0));
        box.addView(text("Kapsi-Q ne répond pas à l'adresse\n" + server + "\n\nVérifiez que le PC du cabinet est allumé, que la fenêtre Kapsi-Q est ouverte et que le téléphone est sur le Wi-Fi du cabinet.", 15, 0xFFF3DDE8, false), lp(16));
        Button retry = button("Réessayer", PINK, true);
        retry.setOnClickListener(v -> openServer(server));
        box.addView(retry, lp(28));
        Button change = button("Changer d'adresse", 0xFFE6C6D8, false);
        change.setOnClickListener(v -> { prefs.edit().remove(KEY_SERVER).apply(); showSetup(null); });
        box.addView(change, lp(12));
        root.addView(box, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        web = null;
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (web == null) { super.onBackPressed(); return; }
        // Le bouton retour d'Android déclenche le bouton « ‹ » de Kapsi-Q quand il est visible
        web.evaluateJavascript("(function(){var b=document.getElementById('back');if(b&&!b.classList.contains('hidden')){b.click();return 'ok';}return 'no';})()",
                r -> { if (!"\"ok\"".equals(r)) finish(); });
    }

    /** Fonctions natives appelées par Kapsi-Q (window.KapsiNative). */
    private class Bridge {
        @JavascriptInterface
        public void saveFile(String name, String mime, String b64) {
            try {
                byte[] data = Base64.decode(b64, Base64.DEFAULT);
                ContentValues cv = new ContentValues();
                cv.put(MediaStore.Downloads.DISPLAY_NAME, name);
                cv.put(MediaStore.Downloads.MIME_TYPE, mime);
                cv.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Kapsi-Q");
                final Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                if (uri == null) throw new IllegalStateException("insert");
                try (OutputStream out = getContentResolver().openOutputStream(uri)) {
                    if (out == null) throw new IllegalStateException("stream");
                    out.write(data);
                }
                runOnUiThread(() -> {
                    Toast.makeText(MainActivity.this, "Enregistré dans Téléchargements/Kapsi-Q", Toast.LENGTH_LONG).show();
                    Intent open = new Intent(Intent.ACTION_VIEW);
                    open.setDataAndType(uri, mime);
                    open.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    try {
                        startActivity(Intent.createChooser(open, "Ouvrir avec"));
                    } catch (ActivityNotFoundException e) {
                        Toast.makeText(MainActivity.this, "Installez Word ou Google Docs pour ouvrir ce fichier.", Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Échec de l'enregistrement du fichier.", Toast.LENGTH_LONG).show());
            }
        }

        @JavascriptInterface
        public void print(final String title) {
            runOnUiThread(() -> {
                if (web == null) return;
                PrintManager pm = (PrintManager) getSystemService(PRINT_SERVICE);
                String job = (title == null || title.isEmpty()) ? "Kapsi-Q" : title;
                pm.print(job, web.createPrintDocumentAdapter(job), new PrintAttributes.Builder().build());
            });
        }

        @JavascriptInterface
        public void changeServer() {
            runOnUiThread(() -> { prefs.edit().remove(KEY_SERVER).apply(); showSetup(null); });
        }

        @JavascriptInterface
        public String version() {
            return "1.0.0";
        }
    }
}
