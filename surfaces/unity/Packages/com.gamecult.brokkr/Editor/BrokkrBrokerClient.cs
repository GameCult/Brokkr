using System;
using System.IO;
using System.Net;
using System.Text;
using GameCult.Brokkr;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    internal static class BrokkrBrokerClient
    {
        internal static string GetHealth(string endpoint)
        {
            return Send(endpoint, "/health", "GET", null);
        }

        internal static BrokkrSnapshotReceipt PublishUnitySnapshot(string endpoint, BrokkrHostSnapshot snapshot)
        {
            var json = JsonUtility.ToJson(snapshot);
            var response = Send(endpoint, "/hosts/unity/snapshot", "POST", json);
            return JsonUtility.FromJson<BrokkrSnapshotReceipt>(response);
        }

        private static string Send(string endpoint, string path, string method, string body)
        {
            var request = (HttpWebRequest)WebRequest.Create(endpoint.TrimEnd('/') + path);
            request.Method = method;
            request.Timeout = 2500;
            request.ReadWriteTimeout = 2500;
            request.Accept = "application/json";

            if (body != null)
            {
                var bytes = Encoding.UTF8.GetBytes(body);
                request.ContentType = "application/json";
                request.ContentLength = bytes.Length;
                using var requestStream = request.GetRequestStream();
                requestStream.Write(bytes, 0, bytes.Length);
            }

            try
            {
                using var response = (HttpWebResponse)request.GetResponse();
                using var responseStream = response.GetResponseStream();
                using var reader = new StreamReader(responseStream ?? Stream.Null);
                return reader.ReadToEnd();
            }
            catch (WebException error) when (error.Response != null)
            {
                using var responseStream = error.Response.GetResponseStream();
                using var reader = new StreamReader(responseStream ?? Stream.Null);
                throw new InvalidOperationException(reader.ReadToEnd());
            }
        }
    }
}

