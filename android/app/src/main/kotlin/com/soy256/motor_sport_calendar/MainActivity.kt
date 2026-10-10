package com.soy256.motor_sport_calendar

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import android.Manifest
import android.os.Build
import android.content.pm.PackageManager
import android.app.NotificationManager
import android.provider.Settings
import android.content.Intent

class MainActivity : FlutterActivity() {
    private var permissionResult: MethodChannel.Result? = null
    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        MethodChannel(engine.dartExecutor.binaryMessenger, "secar/notifications").setMethodCallHandler { call, result ->
            when (call.method) {
                "permission" -> {
                    if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                        permissionResult = result
                        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 700)
                    } else {
                        val allowed = getSystemService(NotificationManager::class.java).areNotificationsEnabled()
                        if (!allowed) startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName))
                        result.success(allowed)
                    }
                }
                "schedule" -> {
                    val json = call.arguments as String
                    getSharedPreferences("secar_reminders", MODE_PRIVATE).edit().putString("entries", json).apply()
                    SessionReminder.schedule(this, json)
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }
    override fun onRequestPermissionsResult(code: Int, permissions: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(code, permissions, results)
        if (code == 700) {
            permissionResult?.success(results.isNotEmpty() && results[0] == PackageManager.PERMISSION_GRANTED)
            permissionResult = null
        }
    }
}
