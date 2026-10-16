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
      textTheme: base.textTheme.copyWith(
        displaySmall: const TextStyle(fontFamily: 'sans-serif', fontSize: 34, height: 1.24, fontWeight: FontWeight.w700, color: AppColors.ink900),
        headlineMedium: const TextStyle(fontFamily: 'sans-serif', fontSize: 28, height: 1.28, fontWeight: FontWeight.w700, color: AppColors.ink900),
        headlineSmall: const TextStyle(fontFamily: 'sans-serif', fontSize: 24, height: 1.3, fontWeight: FontWeight.w700, color: AppColors.ink900),
        titleLarge: const TextStyle(fontFamily: 'sans-serif', fontSize: 21, height: 1.38, fontWeight: FontWeight.w700, color: AppColors.ink900),
        titleMedium: const TextStyle(fontFamily: 'sans-serif', fontSize: 18, height: 1.44, fontWeight: FontWeight.w700, color: AppColors.ink900),
        titleSmall: const TextStyle(fontFamily: 'sans-serif', fontSize: 14, height: 1.4, fontWeight: FontWeight.w700, color: AppColors.ink900),
        bodyLarge: const TextStyle(fontFamily: 'sans-serif', fontSize: 16, height: 1.5, color: AppColors.ink900),
        bodyMedium: const TextStyle(fontFamily: 'sans-serif', fontSize: 14, height: 1.57, color: AppColors.ink900),
        bodySmall: const TextStyle(fontFamily: 'sans-serif', fontSize: 12, height: 1.5, color: AppColors.ink600),
        labelLarge: const TextStyle(fontFamily: 'sans-serif', fontSize: 14, height: 1.42, fontWeight: FontWeight.w700, color: AppColors.ink900),
        labelMedium: const TextStyle(fontFamily: 'sans-serif', fontSize: 12, height: 1.4, fontWeight: FontWeight.w600, color: AppColors.ink700),
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
        labelStyle: TextStyle(color: AppColors.ink600),
        floatingLabelStyle: TextStyle(color: AppColors.brand600, fontWeight: FontWeight.w700),
        hintStyle: TextStyle(color: AppColors.ink600),
        iconColor: AppColors.ink700,
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
