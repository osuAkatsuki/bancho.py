using Newtonsoft.Json;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;
using System;
using System.Text;

class Program
{
    public static void Main()
    {
        Config config = new Config();

        // Ensure the config file exists
        if (!File.Exists("config.json"))
        {
            config.Save("config.json");
            Log("Default config.json created. Set up the config file and re-run the service.", ConsoleColor.Magenta);
            return;
        }

        // Try to deserialize the config file
        try
        {
            config = Config.Load("config.json") ?? new Config();
            Log("Config loaded.", ConsoleColor.Magenta);
        }
        catch (Exception ex)
        {
            Log("An error occured while parsing the config file:", ConsoleColor.Red);
            Log(ex.Message, ConsoleColor.Red);
        }

        // Save the config file again to get rid of all old config settings
        config.Save("config.json");


        ScoreQueue queue = new ScoreQueue(config.RabbitMQHostname, config.RabbitMQPort);

        // Try to connect to the RabbitMQ broker and establish the consumer connection
        try
        {
            queue.Connect();
        }
        catch (Exception ex)
        {
            Log("An error occured while setting up the RabbitMQ consumer:", ConsoleColor.Red);
            Log(ex.Message, ConsoleColor.Red);
            return;
        }

        while (true)
        {
            // Wait until the queue contains a new score
            while (queue.Count == 0)
                ;

            // Dequeue the score id and process it
            ulong id = queue.Dequeue();
            Console.WriteLine($"Processing score with ID {id}", ConsoleColor.Green);
        }
    }

    public static void Log(string message, ConsoleColor color = ConsoleColor.Gray)
    {
        Console.ForegroundColor = ConsoleColor.DarkGray;
        Console.Write($"[{DateTime.UtcNow:HH:mm:sstt}] ");
        Console.ForegroundColor = color;
        Console.WriteLine(message);
    }
}