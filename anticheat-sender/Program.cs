using System;
using RabbitMQ.Client;
using System.Text;

class Send
{
    public static void Main()
    {
        var factory = new ConnectionFactory() { HostName = "localhost" };
        using (var connection = factory.CreateConnection())
        using (var channel = connection.CreateModel())
        {
            channel.QueueDeclare(queue: "bpy.anticheat.score_queue",
                                 durable: true,
                                 exclusive: false,
                                 autoDelete: false,
                                 arguments: null);

            while (true)
            {
                ulong id = ulong.Parse(Console.ReadLine()!);
                channel.BasicPublish(exchange: "",
                                     routingKey: "bpy.anticheat.score_queue",
                                     basicProperties: null,
                                     body: BitConverter.GetBytes(id));
            }
        }
    }
}