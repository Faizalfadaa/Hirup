import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/home/home_screen.dart';
import '../features/history/history_screen.dart';
import '../features/insights/insights_screen.dart';
import '../features/onboarding/onboarding_screen.dart';
import '../features/profile/profile_screen.dart';
import '../features/route_planning/presentation/planning_screens.dart';
import '../features/route_planning/presentation/providers.dart';
import '../shared/app_shell.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();

final routerProvider = Provider<GoRouter>((ref) => GoRouter(
      navigatorKey: _rootNavigatorKey,
      initialLocation: '/',
      routes: [
        GoRoute(path: '/', builder: (_, __) => const _LaunchGate()),
        GoRoute(
            path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
        StatefulShellRoute.indexedStack(
          builder: (_, __, shell) => AppShell(shell: shell),
          branches: [
            StatefulShellBranch(routes: [
              GoRoute(path: '/home', builder: (_, __) => const HomeScreen())
            ]),
            StatefulShellBranch(routes: [
              GoRoute(
                  path: '/history', builder: (_, __) => const HistoryScreen())
            ]),
            StatefulShellBranch(routes: [
              GoRoute(
                  path: '/insights', builder: (_, __) => const InsightsScreen())
            ]),
            StatefulShellBranch(routes: [
              GoRoute(
                  path: '/profile', builder: (_, __) => const ProfileScreen())
            ]),
          ],
        ),
        GoRoute(
            parentNavigatorKey: _rootNavigatorKey,
            path: '/plan/mode',
            builder: (_, __) => const JourneyPreferencesScreen()),
        GoRoute(
            parentNavigatorKey: _rootNavigatorKey,
            path: '/plan/results',
            builder: (_, __) => const ResultsScreen()),
        GoRoute(
            parentNavigatorKey: _rootNavigatorKey,
            path: '/plan/detail/:id',
            builder: (_, state) =>
                DetailScreen(optionId: state.pathParameters['id']!)),
        GoRoute(
            parentNavigatorKey: _rootNavigatorKey,
            path: '/plan/departure',
            builder: (_, __) => const DepartureScreen()),
        GoRoute(
            parentNavigatorKey: _rootNavigatorKey,
            path: '/trip/active',
            builder: (_, __) => const ActiveTripScreen()),
      ],
    ));

class _LaunchGate extends ConsumerWidget {
  const _LaunchGate();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(onboardingCompleteProvider, (_, next) {
      next.whenData((done) => context.go(done ? '/home' : '/onboarding'));
    });
    return const Scaffold(body: Center(child: CircularProgressIndicator()));
  }
}
