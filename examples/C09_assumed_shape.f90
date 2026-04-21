! C09: Assumed-shape dummy array
program assumed_shape
    implicit none
    integer, dimension(10) :: arr
    
    arr = 5
    ! The construct below will be traced
    call process_array(arr(1:5))
    
contains
    subroutine process_array(A)
        integer, dimension(:), intent(in) :: A
        print *, A(1)
    end subroutine
end program assumed_shape
