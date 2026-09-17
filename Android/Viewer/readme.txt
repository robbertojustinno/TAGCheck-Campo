TAGCheck Viewer Android - Offline Parcial

O que esta versão faz:
- Abre o Viewer sem internet, carregando os arquivos locais dentro do APK.
- Usa a câmera do WebView para ler QR Code.
- Quando houver internet, consulta a API do TAGCheck normalmente.
- Quando não houver internet, ainda abre o leitor e pode exibir dados de QR híbrido/cache local conforme o código do Viewer.

Como gerar o APK:
1. Abra esta pasta no Android Studio.
2. Aguarde o Gradle sincronizar.
3. Build > Clean Project.
4. Build > Build Bundle(s) / APK(s) > Build APK(s).
5. O APK ficará em:
   app/build/outputs/apk/debug/app-debug.apk

Pacote:
com.rovixautomation.tagcheckviewer

Observação:
Service Worker/PWA não funciona em file://, mas os arquivos já estão embutidos no APK, então o app abre sem internet.