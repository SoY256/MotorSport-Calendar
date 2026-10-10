package com.soy256.motor_sport_calendar

import android.app.*
import android.content.*
import android.os.Build
import org.json.JSONArray

class SessionReminder : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val prefs = context.getSharedPreferences("secar_reminders", Context.MODE_PRIVATE)
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            schedule(context, prefs.getString("entries", "[]") ?: "[]")
            return
        }
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) manager.createNotificationChannel(NotificationChannel("sessions", "Session reminders", NotificationManager.IMPORTANCE_DEFAULT))
        val open = context.packageManager.getLaunchIntentForPackage(context.packageName) ?: return
        val pending = PendingIntent.getActivity(context, 0, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(context, "sessions") else Notification.Builder(context)
        val notification = builder
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(intent.getStringExtra("title"))
            .setContentText(intent.getStringExtra("body"))
            .setContentIntent(pending).setAutoCancel(true).build()
        try { manager.notify(intent.getIntExtra("id", 0), notification) } catch (_: SecurityException) { }
    }
    companion object {
        fun schedule(context: Context, json: String) {
            val prefs = context.getSharedPreferences("secar_reminders", Context.MODE_PRIVATE)
            val alarms = context.getSystemService(AlarmManager::class.java)
            for (id in prefs.getStringSet("ids", emptySet()) ?: emptySet()) {
                val old = PendingIntent.getBroadcast(context, id.toInt(), Intent(context, SessionReminder::class.java), PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE)
                if (old != null) { alarms.cancel(old); old.cancel() }
            }
            val entries = JSONArray(json)
            val ids = mutableSetOf<String>()
            for (i in 0 until entries.length()) {
                val entry = entries.getJSONObject(i)
                val time = entry.getLong("time")
                if (time <= System.currentTimeMillis()) continue
                val id = entry.getString("id").hashCode()
                val intent = Intent(context, SessionReminder::class.java).putExtra("id", id).putExtra("title", entry.getString("title")).putExtra("body", entry.getString("body"))
                val pending = PendingIntent.getBroadcast(context, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
                // No special exact-alarm access: Android can delay delivery in battery-saving modes.
                alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, time, pending)
                ids.add(id.toString())
            }
            prefs.edit().putStringSet("ids", ids).apply()
        }
    }
}
