import 'package:intl/intl.dart';

String formatDuration(int seconds) {
  final minutes = (seconds / 60).round();
  if (minutes < 60) return '$minutes mnt';
  final hours = minutes ~/ 60;
  final rest = minutes % 60;
  return rest == 0 ? '$hours jam' : '$hours j $rest mnt';
}

String formatDose(num? value) => value == null ? '—' : '${NumberFormat('0.0', 'id_ID').format(value)} µg';
String formatPm25(num? value) => value == null ? '—' : '${NumberFormat('0.0', 'id_ID').format(value)} µg/m³';
String formatTime(DateTime value) => DateFormat('HH.mm', 'id_ID').format(value.toLocal());
String formatDateTime(DateTime value) => DateFormat('d MMM, HH.mm', 'id_ID').format(value.toLocal());
String formatCurrency(int? value) => value == null ? '—' : NumberFormat.currency(locale: 'id_ID', symbol: 'Rp', decimalDigits: 0).format(value);
