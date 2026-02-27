import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import psutil
from tools.sys_monitor import get_system_metrics

class TestGetSystemMetrics(unittest.TestCase):

    @patch('tools.sys_monitor.psutil.sensors_battery')
    @patch('tools.sys_monitor.psutil.process_iter')
    def test_get_system_metrics(self, mock_process_iter, mock_sensors_battery):
        # --- Test case 1: Plugged in and processes ---
        # Mock battery
        mock_battery = MagicMock()
        mock_battery.percent = 90
        mock_battery.power_plugged = True
        mock_sensors_battery.return_value = mock_battery

        # Mock processes
        mock_procs = []
        for i in range(20):
            proc = MagicMock()
            proc.info = {'pid': i, 'name': f'proc{i}', 'memory_percent': i}
            mock_procs.append(proc)
        
        mock_process_iter.return_value = mock_procs

        metrics = get_system_metrics()

        self.assertIn("Battery: 90% (Plugged In)", metrics)
        self.assertIn("Top 15 RAM Processes:", metrics)
        self.assertEqual(len(metrics.strip().split('\n')), 17)
        self.assertIn("proc19", metrics)
        self.assertNotIn("proc4", metrics)

        # --- Test case 2: On battery and no processes ---
        mock_battery.power_plugged = False
        mock_battery.percent = 50
        mock_process_iter.return_value = []
        
        metrics = get_system_metrics()
        self.assertIn("Battery: 50% (On Battery)", metrics)
        self.assertNotIn("% RAM", metrics)

        # --- Test case 3: No battery ---
        mock_sensors_battery.return_value = None
        
        metrics = get_system_metrics()
        self.assertIn("Battery: N/A% (On Battery)", metrics)

    @patch('tools.sys_monitor.psutil.sensors_battery')
    @patch('tools.sys_monitor.psutil.process_iter')
    def test_process_exceptions(self, mock_process_iter, mock_sensors_battery):
        mock_sensors_battery.return_value = None
        
        mock_proc1 = MagicMock()
        type(mock_proc1).info = PropertyMock(side_effect=psutil.NoSuchProcess(1))
        mock_proc2 = MagicMock()
        type(mock_proc2).info = PropertyMock(side_effect=psutil.AccessDenied(2))
        
        mock_proc3 = MagicMock()
        mock_proc3.info = {'pid': 3, 'name': 'proc3', 'memory_percent': 30.0}
        mock_process_iter.return_value = [mock_proc1, mock_proc2, mock_proc3]

        metrics = get_system_metrics()
        self.assertIn("proc3 (PID 3): 30.0% RAM", metrics)
        self.assertNotIn("proc1", metrics)
        self.assertNotIn("proc2", metrics)

    @patch('tools.sys_monitor.psutil.sensors_battery')
    @patch('tools.sys_monitor.psutil.process_iter')
    def test_process_memory_none(self, mock_process_iter, mock_sensors_battery):
        mock_sensors_battery.return_value = None
        mock_proc1 = MagicMock()
        mock_proc1.info = {'pid': 1, 'name': 'proc1', 'memory_percent': None}
        mock_proc2 = MagicMock()
        mock_proc2.info = {'pid': 2, 'name': 'proc2', 'memory_percent': 10.0}
        mock_process_iter.return_value = [mock_proc1, mock_proc2]

        metrics = get_system_metrics()
        self.assertIn("proc2 (PID 2): 10.0% RAM", metrics)
        self.assertIn("proc1 (PID 1): 0.0% RAM", metrics)