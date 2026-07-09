@echo off
echo RTSP modu — .env dosyasinda su satirlari ayarlayin:
echo.
echo   CAMERA_INPUT_TYPE=rtsp
echo   CAMERA_SOURCE=rtsp://KULLANICI:SIFRE@IP:554/stream1
echo   RTSP_BUFFER_SIZE=1
echo.
echo Sonra: .\run_kamera.bat
echo.
echo Ornek IP kamera URL formatlari:
echo   rtsp://admin:12345@192.168.1.64:554/Streaming/Channels/101
echo   rtsp://192.168.1.100:8554/live
pause
