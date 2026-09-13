import 'package:flutter/material.dart';

abstract final class MotorsportTheme {
  static const racingRed = Color(0xFFE10600);
  static const electricBlue = Color(0xFF168BFF);

  static ThemeData get dark => _theme(
    brightness: Brightness.dark,
    surface: const Color(0xFF111418),
    scaffold: const Color(0xFF07090C),
    elevated: const Color(0xFF191D22),
    text: const Color(0xFFF7F8FA),
    outline: const Color(0xFF353B44),
  );

  static ThemeData get light => _theme(
    brightness: Brightness.light,
    surface: const Color(0xFFFFFFFF),
    scaffold: const Color(0xFFF1F3F6),
    elevated: const Color(0xFFF8F9FB),
    text: const Color(0xFF101319),
    outline: const Color(0xFFD7DCE3),
  );

  static ThemeData _theme({
    required Brightness brightness,
    required Color surface,
    required Color scaffold,
    required Color elevated,
    required Color text,
    required Color outline,
  }) {
    final dark = brightness == Brightness.dark;
    final scheme =
        ColorScheme.fromSeed(
          seedColor: racingRed,
          brightness: brightness,
          surface: surface,
        ).copyWith(
          primary: racingRed,
          secondary: electricBlue,
          surfaceContainer: elevated,
          surfaceContainerLow: dark
              ? const Color(0xFF0E1115)
              : const Color(0xFFF8F9FB),
          surfaceContainerHigh: dark
              ? const Color(0xFF20252B)
              : const Color(0xFFEEF1F5),
          outline: outline,
          outlineVariant: outline.withValues(alpha: .72),
        );
    final baseText = ThemeData(brightness: brightness).textTheme
        .apply(bodyColor: text, displayColor: text, fontFamily: 'Roboto');
    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Roboto',
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: scaffold,
      dividerColor: outline,
      splashColor: racingRed.withValues(alpha: .10),
      highlightColor: racingRed.withValues(alpha: .05),
      textTheme: baseText.copyWith(
        headlineLarge: baseText.headlineLarge?.copyWith(
          fontWeight: FontWeight.w900,
          letterSpacing: -1.2,
        ),
        headlineMedium: baseText.headlineMedium?.copyWith(
          fontWeight: FontWeight.w900,
          letterSpacing: -.8,
        ),
        titleLarge: baseText.titleLarge?.copyWith(fontWeight: FontWeight.w900),
        titleMedium: baseText.titleMedium?.copyWith(
          fontWeight: FontWeight.w800,
        ),
      ),
      cardTheme: CardThemeData(
        color: surface.withValues(alpha: dark ? .86 : .96),
        elevation: dark ? 0 : 2,
        shadowColor: Colors.black.withValues(alpha: .12),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: outline.withValues(alpha: .85)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: elevated,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: outline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: racingRed, width: 2),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 74,
        elevation: 0,
        backgroundColor: dark ? const Color(0xFF0D1014) : Colors.white,
        indicatorColor: racingRed.withValues(alpha: dark ? .22 : .12),
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected)
                ? racingRed
                : scheme.onSurfaceVariant,
          ),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            fontSize: 11,
            letterSpacing: .2,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w900
                : FontWeight.w700,
            color: states.contains(WidgetState.selected)
                ? racingRed
                : scheme.onSurfaceVariant,
          ),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: dark ? const Color(0xFF0D1014) : Colors.white,
        indicatorColor: racingRed.withValues(alpha: .16),
        selectedIconTheme: const IconThemeData(color: racingRed),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
          side: WidgetStateProperty.all(BorderSide(color: outline)),
          backgroundColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? racingRed.withValues(alpha: dark ? .25 : .12)
                : elevated,
          ),
          foregroundColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? (dark ? Colors.white : racingRed)
                : scheme.onSurface,
          ),
          textStyle: WidgetStateProperty.all(
            const TextStyle(fontWeight: FontWeight.w800),
          ),
        ),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (states) =>
              states.contains(WidgetState.selected) ? Colors.white : null,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected) ? racingRed : null,
        ),
      ),
    );
  }
}
