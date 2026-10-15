package ma.imrane.clients;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.test.context.*;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,properties={"eureka.client.enabled=false","spring.cloud.consul.enabled=false","spring.cloud.discovery.client.simple.instances.SERVICE-VOITURE[0].uri=${upstream.url}"})
class ClientsIntegrationTest {
    static HttpServer upstream;
    static String base=start();
    static String start() {try {
        upstream=HttpServer.create(new InetSocketAddress("localhost",0),0);
        upstream.createContext("/api/cars/byClient/",exchange->{byte[] data="{\"id\":10,\"marque\":\"Toyota\",\"modele\":\"Yaris\",\"clientId\":1,\"details\":\"test\"}".getBytes();exchange.getResponseHeaders().add("Content-Type","application/json");exchange.sendResponseHeaders(200,data.length);exchange.getResponseBody().write(data);exchange.close();});upstream.start();return "http://localhost:"+upstream.getAddress().getPort();
    }catch(Exception e){throw new IllegalStateException(e);}}
    @DynamicPropertySource static void properties(DynamicPropertyRegistry registry){registry.add("upstream.url",()->base);}
    @AfterAll static void stop(){upstream.stop(0);}
    @Autowired TestRestTemplate http;
    @Test void restTemplateResolvesLogicalName(){assertEquals("Toyota",http.getForObject("/api/clients/1/car/rest",Car.class).marque());}
    @Test void feignResolvesLogicalName(){assertEquals("Toyota",http.getForObject("/api/clients/1/car/feign",Car.class).marque());}
    @Test void webClientResolvesLogicalName(){assertEquals("Toyota",http.getForObject("/api/clients/1/car/webclient",Car.class).marque());}
}
