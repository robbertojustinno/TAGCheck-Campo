package com.rovixautomation.tagcheckviewer;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import android.view.ViewGroup;

import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

public class MainActivity extends Activity {
    private static final String LOCAL_APP_URL = "file:///android_asset/index.html";
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestCameraPermissionIfNeeded();

        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        setContentView(webView);

        configureWebView();

        webView.loadUrl(LOCAL_APP_URL);
    }

    private void requestCameraPermissionIfNeeded() {
        if (android.os.Build.VERSION.SDK_INT >= 23) {
            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.CAMERA}, 10);
            }
        }
    }

    private void configureWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                injectNativeScannerHook();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> request.grant(request.getResources()));
            }
        });
    }

    private void injectNativeScannerHook() {
        String js =
                "(function(){"
                + "function bind(){"
                + "  var btn=document.getElementById('startScanner');"
                + "  if(btn && !btn.dataset.androidNative){"
                + "    btn.dataset.androidNative='1';"
                + "    btn.textContent='Iniciar câmera';"
                + "    btn.onclick=function(e){"
                + "      e.preventDefault();"
                + "      if(window.AndroidScanner){ window.AndroidScanner.scan(); }"
                + "      return false;"
                + "    };"
                + "    var reader=document.getElementById('reader');"
                + "    if(reader){ reader.style.display='none'; }"
                + "    var fb=document.getElementById('scannerFeedback');"
                + "    if(fb){ fb.innerHTML='<div class=\"notice\">Use o botão Iniciar câmera para abrir o leitor nativo Android.</div>'; }"
                + "  }"
                + "}"
                + "bind(); setInterval(bind,700);"
                + "})();";
        webView.evaluateJavascript(js, null);

        webView.addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public void scan() {
                runOnUiThread(() -> startNativeQrScanner());
            }
        }, "AndroidScanner");
    }

    private void startNativeQrScanner() {
        if (android.os.Build.VERSION.SDK_INT >= 23) {
            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.CAMERA}, 10);
                Toast.makeText(this, "Permita a câmera e toque novamente em Iniciar câmera.", Toast.LENGTH_LONG).show();
                return;
            }
        }

        try {
            IntentIntegrator integrator = new IntentIntegrator(this);
            integrator.setPrompt("Aponte para o QR Code da etiqueta");
            integrator.setBeepEnabled(true);
            integrator.setOrientationLocked(false);
            integrator.setDesiredBarcodeFormats(IntentIntegrator.QR_CODE);
            integrator.initiateScan();
        } catch (Exception e) {
            Toast.makeText(this, "Erro ao abrir leitor QR: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private String extractValue(String content, String key) {
        if (content == null) return null;
        String normalized = content.replace("\\r", "\\n");
        String[] lines = normalized.split("\\n");
        for (String line : lines) {
            String clean = line.trim();
            String upper = clean.toUpperCase();
            String k = key.toUpperCase();
            if (upper.startsWith(k + ":")) return clean.substring(clean.indexOf(":") + 1).trim();
            if (upper.startsWith(k + "=")) return clean.substring(clean.indexOf("=") + 1).trim();
        }

        String[] parts = normalized.split("\\|");
        for (String part : parts) {
            String clean = part.trim();
            String upper = clean.toUpperCase();
            String k = key.toUpperCase();
            if (upper.startsWith(k + ":")) return clean.substring(clean.indexOf(":") + 1).trim();
            if (upper.startsWith(k + "=")) return clean.substring(clean.indexOf("=") + 1).trim();
        }
        return null;
    }

    private void openQrResult(String content) {
        if (content == null || content.trim().isEmpty()) {
            Toast.makeText(this, "QR vazio.", Toast.LENGTH_LONG).show();
            return;
        }

        String raw = content.trim();
        String tag = null;
        String id = null;

        try {
            Uri uri = Uri.parse(raw);
            String scheme = uri.getScheme();
            if (scheme != null && (scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https") || scheme.equalsIgnoreCase("file"))) {
                tag = uri.getQueryParameter("tag");
                if (tag == null) tag = uri.getQueryParameter("codigo");
                if (tag == null) tag = uri.getQueryParameter("code");
                id = uri.getQueryParameter("id");
            }
        } catch (Exception ignored) {}

        if (tag == null) tag = extractValue(raw, "TAG");
        if (tag == null) tag = extractValue(raw, "CODIGO");
        if (tag == null) tag = extractValue(raw, "CODE");
        if (id == null) id = extractValue(raw, "ID");

        String finalUrl;
        if (tag != null && !tag.trim().isEmpty()) {
            finalUrl = LOCAL_APP_URL + "?tag=" + Uri.encode(tag.trim());
        } else if (id != null && !id.trim().isEmpty()) {
            finalUrl = LOCAL_APP_URL + "?id=" + Uri.encode(id.trim());
        } else {
            finalUrl = LOCAL_APP_URL + "?tag=" + Uri.encode(raw);
        }

        webView.loadUrl(finalUrl);
        Toast.makeText(this, "QR lido.", Toast.LENGTH_SHORT).show();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, android.content.Intent data) {
        IntentResult result = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (result != null) {
            if (result.getContents() == null) {
                Toast.makeText(this, "Leitura cancelada.", Toast.LENGTH_SHORT).show();
            } else {
                openQrResult(result.getContents());
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}