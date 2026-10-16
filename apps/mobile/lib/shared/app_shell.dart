import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/app_theme.dart';

class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.shell});
  final StatefulNavigationShell shell;

  static const items = <(IconData, IconData, String)>[
    (Icons.explore_outlined, Icons.explore, 'Beranda'),
    (Icons.route_outlined, Icons.route, 'Riwayat'),
    (Icons.blur_on_outlined, Icons.blur_on, 'Insight'),
    (Icons.person_outline, Icons.person, 'Profil'),
  ];

  @override
  Widget build(BuildContext context) => Scaffold(
    body: shell,
    bottomNavigationBar: Container(
      decoration: const BoxDecoration(
        color: AppColors.ink900,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: [BoxShadow(color: Color(0x22073C3B), blurRadius: 24, offset: Offset(0, -8))],
      ),
      child: SafeArea(top: false, child: SizedBox(
        height: 74,
        child: Row(children: List.generate(items.length, (index) {
          final selected = shell.currentIndex == index;
          final item = items[index];
          return Expanded(child: Semantics(
            selected: selected,
            button: true,
            label: item.$3,
            child: InkWell(
              onTap: () => shell.goBranch(index, initialLocation: index == shell.currentIndex),
              child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  height: 34,
                  padding: EdgeInsets.symmetric(horizontal: selected ? 16 : 8),
                  decoration: BoxDecoration(color: selected ? AppColors.mint300 : Colors.transparent, borderRadius: BorderRadius.circular(99)),
                  child: Icon(selected ? item.$2 : item.$1, size: 21, color: selected ? AppColors.ink900 : Colors.white70),
                ),
                const SizedBox(height: 4),
                Text(item.$3, style: TextStyle(fontSize: 10, letterSpacing: .2, fontWeight: selected ? FontWeight.w800 : FontWeight.w600, color: selected ? AppColors.mint300 : Colors.white60)),
              ]),
            ),
          ));
        })),
      )),
    ),
  );
}
