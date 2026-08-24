import 'package:flutter/material.dart';

abstract final class MotorsportTheme {
  static const _red = Color(0xFFE10600);

  static ThemeData get dark => _theme(
    brightness: Brightness.dark,
    surface: const Color(0xFF15171A),
    scaffold: const Color(0xFF0C0D0F),
    text: const Color(0xFFF5F5F5),
  );

  static ThemeData get light => _theme(
    brightness: Brightness.light,
    surface: const Color(0xFFFFFFFF),
    scaffold: const Color(0xFFF3F4F6),
    text: const Color(0xFF16181C),
  );

  static ThemeData _theme({
    required Brightness brightness,
    required Color surface,
    required Color scaffold,
    required Color text,
  }) {
    final scheme = ColorScheme.fromSeed(
      seedColor: _red,
      brightness: brightness,
      surface: surface,
    );
    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: scaffold,
      textTheme: ThemeData(brightness: brightness).textTheme
          .apply(bodyColor: text, displayColor: text),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: scheme.outlineVariant.withValues(alpha: .55)),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 72,
        backgroundColor: surface,
        indicatorColor: _red.withValues(alpha: .16),
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
        ),
      ),
    );
  }
}
