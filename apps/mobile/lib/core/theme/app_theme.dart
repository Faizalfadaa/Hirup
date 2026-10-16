import 'package:flutter/material.dart';

abstract final class AppColors {
  static const brand900 = Color(0xFF073C3B);
  static const brand800 = Color(0xFF07564F);
  static const brand600 = Color(0xFF086A60);
  static const brand100 = Color(0xFFDFF5E8);
  static const mint300 = Color(0xFFB9F4D0);
  static const sky300 = Color(0xFFA9DEFA);
  static const sky700 = Color(0xFF355B69);
  static const sun300 = Color(0xFFFFD27A);
  static const paper = Color(0xFFF7F9F6);
  static const surfaceMint = Color(0xFFE9F6EF);
  static const surfaceSky = Color(0xFFEDF5F8);
  static const ink900 = Color(0xFF102F30);
  static const ink700 = Color(0xFF405B59);
  static const ink600 = Color(0xFF526661);
  static const stroke = Color(0xFFDCE8E1);
  static const danger700 = Color(0xFFA14336);
  static const danger100 = Color(0xFFFAEDE9);
}

abstract final class AppTheme {
  static ThemeData get light {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.brand600,
      brightness: Brightness.light,
      primary: AppColors.brand600,
      surface: Colors.white,
      error: AppColors.danger700,
    );
    final base = ThemeData(useMaterial3: true, colorScheme: scheme);
    return base.copyWith(
      scaffoldBackgroundColor: AppColors.paper,
      textTheme: base.textTheme.apply(
        bodyColor: AppColors.ink900,
        displayColor: AppColors.ink900,
        fontFamily: 'sans-serif',
      ).copyWith(
        displaySmall: const TextStyle(fontSize: 34, height: 1.24, fontWeight: FontWeight.w700),
        headlineMedium: const TextStyle(fontSize: 28, height: 1.28, fontWeight: FontWeight.w700),
        titleLarge: const TextStyle(fontSize: 21, height: 1.38, fontWeight: FontWeight.w700),
        titleMedium: const TextStyle(fontSize: 18, height: 1.44, fontWeight: FontWeight.w700),
        bodyMedium: const TextStyle(fontSize: 14, height: 1.57),
        labelLarge: const TextStyle(fontSize: 14, height: 1.42, fontWeight: FontWeight.w700),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.paper,
        foregroundColor: AppColors.ink900,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
      ),
      cardTheme: const CardThemeData(
        color: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(20)),
          side: BorderSide(color: AppColors.stroke),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 52),
          side: const BorderSide(color: AppColors.stroke),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(16)),
          borderSide: BorderSide(color: AppColors.stroke),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(16)),
          borderSide: BorderSide(color: AppColors.stroke),
        ),
      ),
      navigationBarTheme: const NavigationBarThemeData(
        height: 76,
        backgroundColor: Colors.white,
        indicatorColor: AppColors.brand100,
        labelTextStyle: WidgetStatePropertyAll(TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
      ),
    );
  }
}
