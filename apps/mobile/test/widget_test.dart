import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hirup/app/app.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('HirupApp starts and renders its first screen', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await initializeDateFormatting('id_ID');
    await tester.pumpWidget(const ProviderScope(child: HirupApp()));
    await tester.pump();
    expect(find.byType(MaterialApp), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
