TAGCheck Viewer APK - tentativa final funcional

O que foi corrigido:
- Removido o botão flutuante feio.
- O botão visual normal "Iniciar câmera" do Viewer agora chama o leitor QR nativo Android.
- Removida a declaração manual da CaptureActivity no Manifest para evitar conflito.
- Adicionado android.useAndroidX=true.
- Scanner ZXing integrado.
- App continua abrindo o Viewer local em file:///android_asset/index.html.

Como gerar:
1. Abra a pasta no Android Studio.
2. Clique em Sync Now.
3. Build > Clean Project.
4. Build > Rebuild Project.
5. Build > Build APK(s).

Se der erro:
- Envie o erro completo do Build Output.
- Se instalar sobre APK antigo, desinstale o antigo antes.