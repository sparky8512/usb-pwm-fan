using FanControl.Plugins;
using System;
using System.IO;
using System.Reflection;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Threading;

namespace UsbFanPlugin_Test
{
    /// <summary>
    /// Executable for testing UsbFanPlugin plugin lib without having to start
    /// up FanControl
    /// </summary>
    internal class Program
    {
        private const int InitialFanDelayMilliseconds = 250;
        private const int FanDelayMilliseconds = 2500;

        static void Main()
        {
            string[] args = Environment.GetCommandLineArgs();
            if (args.Length < 2)
            {
                Console.WriteLine("Usage:");
                Console.WriteLine($"    {args[0]} PLUGIN_LIB_DLL_PATH [TEST_MODE]");
                return;
            }

            string mode;
            if (args.Length > 2)
            {
                mode = args[2];
                if (mode != "hotplug")
                {
                    mode = "speed";
                }
            } else
            {
                mode = "speed";
            }
            string path = Path.GetFullPath(args[1]);
            Type pluginType = typeof(IPlugin);

            Assembly pluginLib = Assembly.LoadFile(path);
            foreach (Type type in pluginLib.GetTypes())
            {
                if (pluginType.IsAssignableFrom(type))
                {
                    RunTest(type, mode);
                }
            }
        }

        private class TestLogger : IPluginLogger
        {
            public void Log(string message)
            {
                Console.WriteLine("Log: " + message);
            }
        }

        private class TestDialog : IPluginDialog
        {
            public Task ShowMessageDialog(string message)
            {
                Console.WriteLine("Dialog: " + message);
                return Task.CompletedTask;
            }
        }

        private class TestContainer : IPluginSensorsContainer
        {
            public List<IPluginControlSensor> ControlSensors { get; }

            public List<IPluginSensor> FanSensors { get; }

            public List<IPluginSensor> TempSensors { get; }

            public TestContainer()
            {
                ControlSensors = new List<IPluginControlSensor>();
                FanSensors = new List<IPluginSensor>();
                TempSensors = new List<IPluginSensor>();
            }
        }

        private static void TestSpeed(IPluginControlSensor control, IPluginSensor sensor)
        {
            sensor.Update();
            Console.WriteLine("    Initial tach reading: " + sensor.Value);

            control.Set(0.0F);
            Thread.Sleep(InitialFanDelayMilliseconds);
            sensor.Update();
            Console.WriteLine("    0% tach reading: " + sensor.Value);

            control.Set(50.0F);
            Thread.Sleep(FanDelayMilliseconds);
            sensor.Update();
            Console.WriteLine("    50% tach reading: " + sensor.Value);

            control.Set(100.0F);
            Thread.Sleep(FanDelayMilliseconds);
            sensor.Update();
            Console.WriteLine("    100% tach reading: " + sensor.Value);

            control.Reset();
        }

        private static void TestHotplug(IPluginControlSensor control, IPluginSensor sensor)
        {
            control.Set(0.0F);
            Thread.Sleep(InitialFanDelayMilliseconds);
            sensor.Update();
            Console.WriteLine("    Initial tach reading: " + sensor.Value);

            Console.WriteLine("    Unplug, then press any key to continue");
            Console.ReadKey(true);
            control.Set(25.0F);
            Thread.Sleep(FanDelayMilliseconds);
            sensor.Update();
            Console.WriteLine("    Unplugged 25% tach reading: " + sensor.Value);

            Console.WriteLine("    Replug, then press any key to continue");
            Console.ReadKey(true);
            control.Set(50.0F);
            Thread.Sleep(FanDelayMilliseconds);
            sensor.Update();
            Console.WriteLine("    Replugged 50% tach reading: " + sensor.Value);

            Console.WriteLine("    Unplug, then replug, then press any key to continue");
            Console.ReadKey(true);
            control.Set(75.0F);
            Thread.Sleep(FanDelayMilliseconds);
            sensor.Update();
            Console.WriteLine("    Un/replugged 75% tach reading: " + sensor.Value);

            control.Reset();
        }

        private static void RunTest(Type type, string mode)
        {
            Console.WriteLine("Testing plugin class: " + type.FullName);

            Type[] ctorParameterTypes = new Type[] { typeof(IPluginLogger), typeof(IPluginDialog) };
            object[] ctorParameters = new object[] { new TestLogger(), new TestDialog() };
            IPlugin plugin = (IPlugin)type.GetConstructor(ctorParameterTypes).Invoke(ctorParameters);

            TestContainer container = new TestContainer();

            plugin.Initialize();
            plugin.Load(container);

            foreach (IPluginSensor sensor in container.ControlSensors)
            {
                Console.WriteLine($"Controller ID '{sensor.Id}', name '{sensor.Name}'");
            }
            foreach (IPluginSensor sensor in container.FanSensors)
            {
                Console.WriteLine($"Fan sensor ID '{sensor.Id}', name '{sensor.Name}'");
            }
            foreach (IPluginSensor sensor in container.TempSensors)
            {
                Console.WriteLine($"Temperature sensor ID '{sensor.Id}', name '{sensor.Name}'");
            }

            int pairs = container.ControlSensors.Count < container.FanSensors.Count ? container.ControlSensors.Count : container.FanSensors.Count;
            for (int i = 0; i < pairs; i++)
            {
                Console.WriteLine($"Testing sensor pair {i} with mode '{mode}'");
                if (mode == "speed")
                {
                    TestSpeed(container.ControlSensors[i], container.FanSensors[i]);
                } else
                {
                    TestHotplug(container.ControlSensors[i], container.FanSensors[i]);
                }
            }

            plugin.Close();
        }
    }
}
