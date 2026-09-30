#include <pqxx/except>

#if pqxx_have_source_location
namespace pqxx {

argument_error::argument_error(std::string const &what, std::source_location loc)
    : std::invalid_argument{what}, location{loc} {}

conversion_error::conversion_error(std::string const &what, std::source_location loc)
    : std::domain_error{what}, location{loc} {}

} // namespace pqxx
#endif
